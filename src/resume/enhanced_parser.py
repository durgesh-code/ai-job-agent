# src/resume/enhanced_parser.py
import json
import re
from typing import Dict, List, Optional, Any
from openai import OpenAI
from ..config import config
from .parser import extract_text_from_file

class EnhancedResumeParser:
    """LLM-powered resume parser for comprehensive profile extraction"""
    
    def __init__(self):
        self.client = OpenAI(api_key=config.openai_api_key)
        self.skill_taxonomy = self._load_skill_taxonomy()
    
    def _load_skill_taxonomy(self) -> Dict[str, List[str]]:
        """Load skill taxonomy for normalization"""
        return {
            "python": ["python", "py", "python3", "django", "flask", "fastapi"],
            "javascript": ["javascript", "js", "node.js", "nodejs", "react", "vue", "angular"],
            "java": ["java", "spring", "spring boot", "hibernate"],
            "machine_learning": ["ml", "machine learning", "tensorflow", "pytorch", "scikit-learn"],
            "data_science": ["data science", "pandas", "numpy", "matplotlib", "seaborn"],
            "cloud": ["aws", "azure", "gcp", "google cloud", "amazon web services"],
            "devops": ["docker", "kubernetes", "jenkins", "ci/cd", "terraform"],
            "databases": ["sql", "mysql", "postgresql", "mongodb", "redis"],
            "frontend": ["html", "css", "react", "vue", "angular", "typescript"],
            "backend": ["api", "rest", "graphql", "microservices", "distributed systems"]
        }
    
    def parse_resume_with_llm(self, resume_text: str) -> Dict[str, Any]:
        """Use LLM to extract structured data from resume"""
        prompt = f"""
        Extract structured information from this resume. Return a JSON object with the following structure:
        
        {{
            "personal_info": {{
                "name": "Full Name",
                "email": "email@example.com",
                "phone": "phone number",
                "location": "City, State/Country",
                "linkedin": "LinkedIn URL",
                "github": "GitHub URL",
                "portfolio": "Portfolio URL"
            }},
            "professional_summary": "Brief professional summary",
            "current_title": "Current or most recent job title",
            "experience_years": 5,
            "career_level": "junior|mid|senior|lead|executive",
            "skills": {{
                "technical": ["skill1", "skill2", "skill3"],
                "programming_languages": ["Python", "JavaScript"],
                "frameworks": ["React", "Django"],
                "tools": ["Docker", "Git"],
                "databases": ["PostgreSQL", "MongoDB"],
                "cloud": ["AWS", "Azure"]
            }},
            "experience": [
                {{
                    "title": "Job Title",
                    "company": "Company Name",
                    "duration": "Jan 2020 - Present",
                    "description": "Brief description of role and achievements",
                    "technologies": ["tech1", "tech2"]
                }}
            ],
            "education": [
                {{
                    "degree": "Degree Name",
                    "institution": "University Name",
                    "year": "2020",
                    "field": "Computer Science"
                }}
            ],
            "certifications": ["AWS Certified", "Google Cloud Professional"],
            "projects": [
                {{
                    "name": "Project Name",
                    "description": "Project description",
                    "technologies": ["tech1", "tech2"],
                    "url": "project URL if available"
                }}
            ],
            "preferred_roles": ["Software Engineer", "Backend Developer"],
            "industries": ["Technology", "Finance", "Healthcare"],
            "work_preferences": {{
                "remote": "remote|hybrid|onsite|flexible",
                "company_size": ["startup", "small", "medium", "large"],
                "role_type": "individual_contributor|management|both"
            }}
        }}
        
        Resume Text:
        {resume_text}
        
        Extract as much information as possible. If information is not available, use null or empty arrays.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert resume parser. Extract structured information accurately and return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            parsed_data = json.loads(response.choices[0].message.content)
            return self._normalize_parsed_data(parsed_data)
            
        except Exception as e:
            print(f"LLM parsing failed: {e}")
            return self._fallback_parsing(resume_text)
    
    def _normalize_parsed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and enhance parsed data"""
        # Normalize skills using taxonomy
        if "skills" in data and "technical" in data["skills"]:
            normalized_skills = []
            for skill in data["skills"]["technical"]:
                normalized_skill = self._normalize_skill(skill.lower())
                if normalized_skill:
                    normalized_skills.append(normalized_skill)
            data["skills"]["technical"] = list(set(normalized_skills))
        
        # Calculate experience years if not provided
        if not data.get("experience_years") and data.get("experience"):
            data["experience_years"] = self._calculate_experience_years(data["experience"])
        
        # Infer career level if not provided
        if not data.get("career_level"):
            data["career_level"] = self._infer_career_level(data)
        
        return data
    
    def _normalize_skill(self, skill: str) -> Optional[str]:
        """Normalize skill name using taxonomy"""
        skill = skill.lower().strip()
        
        for canonical_skill, variations in self.skill_taxonomy.items():
            if skill in variations or skill == canonical_skill:
                return canonical_skill
        
        # Return original if no normalization found
        return skill if len(skill) > 2 else None
    
    def _calculate_experience_years(self, experience: List[Dict]) -> int:
        """Calculate total experience years from job history"""
        total_months = 0
        
        for job in experience:
            duration = job.get("duration", "")
            months = self._parse_duration_to_months(duration)
            total_months += months
        
        return max(1, total_months // 12)
    
    def _parse_duration_to_months(self, duration: str) -> int:
        """Parse duration string to months"""
        duration = duration.lower()
        
        # Look for patterns like "2 years", "6 months", "Jan 2020 - Dec 2022"
        year_match = re.search(r'(\d+)\s*years?', duration)
        month_match = re.search(r'(\d+)\s*months?', duration)
        
        months = 0
        if year_match:
            months += int(year_match.group(1)) * 12
        if month_match:
            months += int(month_match.group(1))
        
        # If no explicit duration, assume 12 months
        return months if months > 0 else 12
    
    def _infer_career_level(self, data: Dict[str, Any]) -> str:
        """Infer career level from experience and titles"""
        experience_years = data.get("experience_years", 0)
        current_title = (data.get("current_title", "")).lower()
        
        # Check title keywords
        if any(keyword in current_title for keyword in ["senior", "lead", "principal", "staff"]):
            return "senior"
        elif any(keyword in current_title for keyword in ["manager", "director", "head", "vp"]):
            return "lead"
        elif any(keyword in current_title for keyword in ["junior", "associate", "entry"]):
            return "junior"
        
        # Fallback to experience years
        if experience_years >= 8:
            return "senior"
        elif experience_years >= 4:
            return "mid"
        elif experience_years >= 1:
            return "junior"
        else:
            return "entry"
    
    def _fallback_parsing(self, resume_text: str) -> Dict[str, Any]:
        """Fallback parsing using regex and heuristics"""
        from .profile import build_profile_from_text
        
        basic_profile = build_profile_from_text(resume_text)
        
        return {
            "personal_info": {
                "name": None,
                "email": self._extract_email(resume_text),
                "phone": self._extract_phone(resume_text),
                "location": None,
                "linkedin": None,
                "github": None,
                "portfolio": None
            },
            "professional_summary": None,
            "current_title": basic_profile.get("title_guess"),
            "experience_years": basic_profile.get("years_experience"),
            "career_level": "mid",
            "skills": {
                "technical": basic_profile.get("skills", []),
                "programming_languages": [],
                "frameworks": [],
                "tools": [],
                "databases": [],
                "cloud": []
            },
            "experience": [],
            "education": [],
            "certifications": [],
            "projects": [],
            "preferred_roles": [],
            "industries": [],
            "work_preferences": {
                "remote": "flexible",
                "company_size": ["medium", "large"],
                "role_type": "individual_contributor"
            }
        }
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number using regex"""
        phone_pattern = r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        match = re.search(phone_pattern, text)
        return match.group(0) if match else None
    
    def parse_resume_file(self, file_path: str) -> Dict[str, Any]:
        """Parse resume from file path"""
        resume_text = extract_text_from_file(file_path)
        return self.parse_resume_with_llm(resume_text)
    
    def create_user_profile(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert parsed resume data to user profile format"""
        return {
            "name": resume_data.get("personal_info", {}).get("name"),
            "email": resume_data.get("personal_info", {}).get("email"),
            "resume_text": resume_data.get("raw_text", ""),
            "skills": resume_data.get("skills", {}).get("technical", []),
            "experience_years": resume_data.get("experience_years"),
            "current_title": resume_data.get("current_title"),
            "preferred_roles": resume_data.get("preferred_roles", []),
            "preferred_locations": [],
            "preferred_remote": resume_data.get("work_preferences", {}).get("remote", "flexible"),
            "preferred_company_size": resume_data.get("work_preferences", {}).get("company_size", []),
            "career_level": resume_data.get("career_level"),
            "target_industries": resume_data.get("industries", []),
            "learning_goals": []
        }

# Global instance
enhanced_parser = EnhancedResumeParser()
