# src/matcher/enhanced_matcher.py
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from ..db import SessionLocal
from ..models import Job, Company, UserProfile, Match, JobApplication
from ..embeddings.encoder import Encoder
from ..embeddings.vector_store import FaissStore
from ..config import config
import re

class EnhancedJobMatcher:
    """Advanced job matching with multi-factor scoring"""
    
    def __init__(self):
        self.encoder = Encoder()
        self.vector_store = FaissStore(d=384)  # all-MiniLM-L6-v2 dimension
        self.weights = config.matching_weights
        self.thresholds = config.matching_thresholds
        
    def calculate_job_scores(self):
        """Calculate and update job attractiveness scores"""
        db = SessionLocal()
        try:
            jobs = db.query(Job).filter(Job.is_active == True).all()
            
            for job in jobs:
                job.job_score = self._calculate_job_attractiveness(job)
                job.freshness_score = self._calculate_freshness_score(job)
                job.competition_level = self._estimate_competition_level(job)
            
            db.commit()
            print(f"Updated scores for {len(jobs)} jobs")
            
        finally:
            db.close()
    
    def _calculate_job_attractiveness(self, job: Job) -> float:
        """Calculate overall job attractiveness score"""
        score = 0.0
        
        # Company score (0.3 weight)
        if job.company and job.company.company_score:
            score += 0.3 * (job.company.company_score / 5.0)  # Normalize to 0-1
        
        # Salary score (0.25 weight)
        if job.salary_min and job.salary_max:
            avg_salary = (job.salary_min + job.salary_max) / 2
            # Normalize salary (assuming 200k as high end)
            salary_score = min(1.0, avg_salary / 200000)
            score += 0.25 * salary_score
        
        # Remote flexibility (0.2 weight)
        remote_scores = {"remote": 1.0, "hybrid": 0.8, "onsite": 0.5}
        remote_score = remote_scores.get(job.remote_option, 0.6)
        score += 0.2 * remote_score
        
        # Benefits score (0.15 weight)
        if job.benefits:
            benefits_score = min(1.0, len(job.benefits) / 10)  # Normalize by 10 benefits
            score += 0.15 * benefits_score
        
        # Experience level appropriateness (0.1 weight)
        exp_score = 0.8  # Default moderate score
        if job.experience_level in ["mid", "senior"]:
            exp_score = 1.0  # These are typically well-defined roles
        elif job.experience_level in ["entry", "junior"]:
            exp_score = 0.7  # May have lower compensation
        score += 0.1 * exp_score
        
        return min(1.0, score)
    
    def _calculate_freshness_score(self, job: Job) -> float:
        """Calculate job freshness score based on posting date"""
        if not job.posted_date:
            return 0.5  # Default for unknown dates
        
        days_old = (datetime.utcnow() - job.posted_date).days
        
        if days_old <= 7:
            return 1.0  # Very fresh
        elif days_old <= 30:
            return 0.8  # Fresh
        elif days_old <= 60:
            return 0.6  # Moderate
        elif days_old <= 90:
            return 0.4  # Getting old
        else:
            return 0.2  # Old posting
    
    def _estimate_competition_level(self, job: Job) -> str:
        """Estimate competition level for the job"""
        score = 0
        
        # High-paying jobs are more competitive
        if job.salary_min and job.salary_min > 150000:
            score += 2
        elif job.salary_min and job.salary_min > 100000:
            score += 1
        
        # Senior roles are more competitive
        if job.experience_level in ["senior", "lead", "principal"]:
            score += 2
        elif job.experience_level == "mid":
            score += 1
        
        # Popular companies are more competitive
        if job.company and job.company.company_score and job.company.company_score > 4.0:
            score += 2
        elif job.company and job.company.company_score and job.company.company_score > 3.5:
            score += 1
        
        # Remote jobs are more competitive
        if job.remote_option == "remote":
            score += 1
        
        if score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"
    
    def match_user_to_jobs(self, user_id: int, top_k: int = 50) -> List[Dict[str, Any]]:
        """Enhanced job matching for a user"""
        db = SessionLocal()
        try:
            user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
            if not user:
                return []
            
            # Get active jobs
            jobs = db.query(Job).filter(Job.is_active == True).all()
            
            # Calculate matches
            matches = []
            for job in jobs:
                match_data = self._calculate_match_score(user, job)
                if match_data["overall_score"] >= self.thresholds.get("minimum_match_score", 0.6):
                    matches.append(match_data)
            
            # Sort by overall score
            matches.sort(key=lambda x: x["overall_score"], reverse=True)
            
            # Store top matches in database
            self._store_matches(user_id, matches[:top_k], db)
            
            return matches[:top_k]
            
        finally:
            db.close()
    
    def _calculate_match_score(self, user: UserProfile, job: Job) -> Dict[str, Any]:
        """Calculate comprehensive match score between user and job"""
        
        # 1. Semantic similarity score
        semantic_score = self._calculate_semantic_score(user, job)
        
        # 2. Skill match score
        skill_match_score, matched_skills, missing_skills = self._calculate_skill_match(user, job)
        
        # 3. Experience match score
        experience_match_score = self._calculate_experience_match(user, job)
        
        # 4. Location match score
        location_match_score = self._calculate_location_match(user, job)
        
        # 5. Salary match score
        salary_match_score = self._calculate_salary_match(user, job)
        
        # 6. Company match score
        company_match_score = self._calculate_company_match(user, job)
        
        # Calculate weighted overall score
        overall_score = (
            self.weights.get("semantic_score", 0.3) * semantic_score +
            self.weights.get("skill_match", 0.25) * skill_match_score +
            self.weights.get("experience_match", 0.2) * experience_match_score +
            self.weights.get("location_match", 0.1) * location_match_score +
            self.weights.get("salary_match", 0.1) * salary_match_score +
            self.weights.get("company_match", 0.05) * company_match_score
        )
        
        # Generate reasons
        reasons = self._generate_match_reasons(
            semantic_score, skill_match_score, experience_match_score,
            matched_skills, job
        )
        
        return {
            "job_id": job.id,
            "job": job,
            "overall_score": overall_score,
            "semantic_score": semantic_score,
            "skill_match_score": skill_match_score,
            "experience_match_score": experience_match_score,
            "location_match_score": location_match_score,
            "salary_match_score": salary_match_score,
            "company_match_score": company_match_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "reasons": reasons
        }
    
    def _calculate_semantic_score(self, user: UserProfile, job: Job) -> float:
        """Calculate semantic similarity between user profile and job"""
        try:
            # Create user text
            user_text = f"{user.current_title or ''} {' '.join(user.skills or [])} {user.resume_text or ''}"
            
            # Create job text
            job_text = f"{job.title or ''} {job.description or ''}"
            
            # Get embeddings
            user_embedding = self.encoder.encode([user_text])[0]
            job_embedding = self.encoder.encode([job_text])[0]
            
            # Calculate cosine similarity
            similarity = np.dot(user_embedding, job_embedding) / (
                np.linalg.norm(user_embedding) * np.linalg.norm(job_embedding)
            )
            
            return max(0.0, min(1.0, similarity))
            
        except Exception:
            return 0.5  # Default score if calculation fails
    
    def _calculate_skill_match(self, user: UserProfile, job: Job) -> tuple:
        """Calculate skill matching score"""
        user_skills = set(skill.lower() for skill in (user.skills or []))
        
        # Extract skills from job
        job_skills = set()
        if job.required_skills:
            job_skills.update(skill.lower() for skill in job.required_skills)
        if job.preferred_skills:
            job_skills.update(skill.lower() for skill in job.preferred_skills)
        
        # Also extract from job description
        if job.description:
            job_skills.update(self._extract_skills_from_text(job.description.lower()))
        
        if not job_skills:
            return 0.5, [], []  # Default if no skills identified
        
        # Calculate matches
        matched_skills = list(user_skills.intersection(job_skills))
        missing_skills = list(job_skills - user_skills)
        
        # Calculate score
        if job_skills:
            skill_score = len(matched_skills) / len(job_skills)
        else:
            skill_score = 0.5
        
        return skill_score, matched_skills, missing_skills
    
    def _extract_skills_from_text(self, text: str) -> set:
        """Extract technical skills from job description text"""
        common_skills = {
            "python", "java", "javascript", "react", "node.js", "sql", "aws", "docker",
            "kubernetes", "git", "linux", "mongodb", "postgresql", "redis", "elasticsearch",
            "tensorflow", "pytorch", "machine learning", "data science", "api", "rest",
            "graphql", "microservices", "agile", "scrum", "ci/cd", "jenkins", "terraform"
        }
        
        found_skills = set()
        for skill in common_skills:
            if skill in text:
                found_skills.add(skill)
        
        return found_skills
    
    def _calculate_experience_match(self, user: UserProfile, job: Job) -> float:
        """Calculate experience level matching"""
        if not user.experience_years or not job.experience_level:
            return 0.7  # Default moderate match
        
        # Define experience ranges
        level_ranges = {
            "entry": (0, 2),
            "junior": (1, 3),
            "mid": (3, 6),
            "senior": (5, 10),
            "lead": (7, 15),
            "principal": (10, 20)
        }
        
        job_range = level_ranges.get(job.experience_level, (0, 20))
        user_exp = user.experience_years
        
        # Perfect match if within range
        if job_range[0] <= user_exp <= job_range[1]:
            return 1.0
        
        # Partial match based on distance from range
        if user_exp < job_range[0]:
            # Under-qualified
            gap = job_range[0] - user_exp
            return max(0.3, 1.0 - (gap * 0.2))
        else:
            # Over-qualified
            gap = user_exp - job_range[1]
            return max(0.6, 1.0 - (gap * 0.1))
    
    def _calculate_location_match(self, user: UserProfile, job: Job) -> float:
        """Calculate location preference matching"""
        if not user.preferred_locations or not job.location:
            return 0.8  # Default good match if no preferences
        
        job_location = job.location.lower()
        
        for pref_location in user.preferred_locations:
            if pref_location.lower() in job_location or job_location in pref_location.lower():
                return 1.0
        
        # Check for remote options
        if job.remote_option in ["remote", "hybrid"]:
            if user.preferred_remote in ["remote", "hybrid", "flexible"]:
                return 0.9
        
        return 0.4  # Poor location match
    
    def _calculate_salary_match(self, user: UserProfile, job: Job) -> float:
        """Calculate salary expectation matching"""
        if not user.preferred_salary_min or not job.salary_min:
            return 0.7  # Default if no salary info
        
        user_min = user.preferred_salary_min
        user_max = user.preferred_salary_max or (user_min * 1.5)
        
        job_min = job.salary_min
        job_max = job.salary_max or job_min
        
        # Check for overlap
        if job_max >= user_min and job_min <= user_max:
            # Calculate overlap percentage
            overlap_start = max(user_min, job_min)
            overlap_end = min(user_max, job_max)
            overlap = overlap_end - overlap_start
            
            user_range = user_max - user_min
            if user_range > 0:
                return min(1.0, overlap / user_range)
            else:
                return 1.0
        
        # No overlap - check how far apart
        if job_max < user_min:
            # Job pays less than expected
            gap = user_min - job_max
            return max(0.2, 1.0 - (gap / user_min))
        else:
            # Job pays more than expected (good!)
            return 1.0
    
    def _calculate_company_match(self, user: UserProfile, job: Job) -> float:
        """Calculate company preference matching"""
        if not job.company:
            return 0.5
        
        score = 0.5  # Base score
        
        # Company size preference
        if user.preferred_company_size and job.company.company_size:
            if job.company.company_size in user.preferred_company_size:
                score += 0.3
        
        # Company rating
        if job.company.glassdoor_rating:
            rating_score = job.company.glassdoor_rating / 5.0
            score += 0.2 * rating_score
        
        return min(1.0, score)
    
    def _generate_match_reasons(self, semantic_score: float, skill_score: float, 
                              exp_score: float, matched_skills: List[str], job: Job) -> List[str]:
        """Generate human-readable reasons for the match"""
        reasons = []
        
        if semantic_score > 0.8:
            reasons.append("Strong semantic match with your background")
        elif semantic_score > 0.6:
            reasons.append("Good alignment with your experience")
        
        if skill_score > 0.7:
            reasons.append(f"Strong skill match: {', '.join(matched_skills[:3])}")
        elif matched_skills:
            reasons.append(f"Skill overlap: {', '.join(matched_skills[:2])}")
        
        if exp_score > 0.8:
            reasons.append("Perfect experience level match")
        elif exp_score > 0.6:
            reasons.append("Good experience level fit")
        
        if job.remote_option == "remote":
            reasons.append("Remote work available")
        elif job.remote_option == "hybrid":
            reasons.append("Hybrid work option")
        
        if job.salary_min and job.salary_min > 100000:
            reasons.append("Competitive salary range")
        
        return reasons
    
    def _store_matches(self, user_id: int, matches: List[Dict], db):
        """Store match results in database"""
        # Clear existing matches for this user
        db.query(Match).filter(Match.user_id == user_id).delete()
        
        # Store new matches
        for match_data in matches:
            match = Match(
                user_id=user_id,
                job_id=match_data["job_id"],
                overall_score=match_data["overall_score"],
                semantic_score=match_data["semantic_score"],
                skill_match_score=match_data["skill_match_score"],
                experience_match_score=match_data["experience_match_score"],
                location_match_score=match_data["location_match_score"],
                salary_match_score=match_data["salary_match_score"],
                company_match_score=match_data["company_match_score"],
                matched_skills=match_data["matched_skills"],
                missing_skills=match_data["missing_skills"],
                reasons=match_data["reasons"]
            )
            db.add(match)
        
        db.commit()

# Global instance
enhanced_matcher = EnhancedJobMatcher()
