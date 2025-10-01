# src/intelligence/company_analyzer.py
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import aiohttp
from bs4 import BeautifulSoup

from ..db import SessionLocal
from ..models import Company, Job
from ..config import config
from ..crawler.llm_client import LLMClient

logger = logging.getLogger(__name__)

class CompanyAnalyzer:
    """Advanced company intelligence with scoring and metadata enrichment"""
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.intelligence_config = config.intelligence_config
        
    async def analyze_company(self, company_id: int) -> Dict:
        """Perform comprehensive company analysis"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                return {}
            
            logger.info(f"Analyzing company: {company.name}")
            
            # Gather company intelligence
            intelligence = await self.gather_company_intelligence(company)
            
            # Calculate company score
            score = self.calculate_company_score(company, intelligence)
            
            # Update company with new intelligence
            self.update_company_metadata(db, company, intelligence, score)
            
            db.commit()
            
            return {
                "company_id": company_id,
                "score": score,
                "intelligence": intelligence
            }
            
        except Exception as e:
            logger.error(f"Error analyzing company {company_id}: {e}")
            return {}
        finally:
            db.close()
    
    async def gather_company_intelligence(self, company: Company) -> Dict:
        """Gather comprehensive intelligence about a company"""
        intelligence = {}
        
        # Web scraping intelligence
        if company.website:
            web_intel = await self.scrape_company_website(company.website)
            intelligence.update(web_intel)
        
        # Social media intelligence
        social_intel = await self.analyze_social_presence(company.name)
        intelligence.update(social_intel)
        
        # Job posting analysis
        job_intel = self.analyze_job_postings(company)
        intelligence.update(job_intel)
        
        # LLM-based analysis
        llm_intel = await self.llm_company_analysis(company, intelligence)
        intelligence.update(llm_intel)
        
        return intelligence
    
    async def scrape_company_website(self, website_url: str) -> Dict:
        """Scrape company website for intelligence"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(website_url, timeout=30) as response:
                    if response.status != 200:
                        return {}
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    intelligence = {}
                    
                    # Extract company description
                    about_text = self.extract_about_section(soup)
                    if about_text:
                        intelligence['web_description'] = about_text[:1000]
                    
                    # Extract technology stack
                    tech_stack = self.extract_tech_stack(html)
                    if tech_stack:
                        intelligence['detected_tech_stack'] = tech_stack
                    
                    # Extract company size indicators
                    size_indicators = self.extract_size_indicators(soup)
                    if size_indicators:
                        intelligence['size_indicators'] = size_indicators
                    
                    # Extract contact information
                    contact_info = self.extract_contact_info(soup)
                    if contact_info:
                        intelligence['contact_info'] = contact_info
                    
                    return intelligence
                    
        except Exception as e:
            logger.error(f"Error scraping website {website_url}: {e}")
            return {}
    
    def extract_about_section(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract about/description section from website"""
        # Look for common about section patterns
        selectors = [
            'section[id*="about"]',
            'div[id*="about"]',
            'section[class*="about"]',
            'div[class*="about"]',
            '.company-description',
            '.about-us',
            'meta[name="description"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                if selector.startswith('meta'):
                    return element.get('content', '')
                else:
                    text = element.get_text(strip=True)
                    if len(text) > 100:  # Reasonable length for description
                        return text
        
        return None
    
    def extract_tech_stack(self, html: str) -> List[str]:
        """Extract technology stack from website HTML"""
        tech_patterns = {
            'react': r'\breact\b',
            'angular': r'\bangular\b',
            'vue': r'\bvue\.js\b|\bvuejs\b',
            'python': r'\bpython\b',
            'javascript': r'\bjavascript\b|\bjs\b',
            'typescript': r'\btypescript\b|\bts\b',
            'node': r'\bnode\.js\b|\bnodejs\b',
            'django': r'\bdjango\b',
            'flask': r'\bflask\b',
            'aws': r'\baws\b|\bamazon web services\b',
            'docker': r'\bdocker\b',
            'kubernetes': r'\bkubernetes\b|\bk8s\b',
            'mongodb': r'\bmongodb\b|\bmongo\b',
            'postgresql': r'\bpostgresql\b|\bpostgres\b',
            'mysql': r'\bmysql\b',
            'redis': r'\bredis\b',
            'elasticsearch': r'\belasticsearch\b'
        }
        
        detected_tech = []
        html_lower = html.lower()
        
        for tech, pattern in tech_patterns.items():
            if re.search(pattern, html_lower):
                detected_tech.append(tech)
        
        return detected_tech
    
    def extract_size_indicators(self, soup: BeautifulSoup) -> Dict:
        """Extract company size indicators"""
        indicators = {}
        
        # Look for employee count mentions
        text = soup.get_text().lower()
        
        # Employee count patterns
        employee_patterns = [
            r'(\d+)\+?\s*employees',
            r'team of (\d+)',
            r'(\d+)\+?\s*people',
            r'(\d+)\+?\s*team members'
        ]
        
        for pattern in employee_patterns:
            match = re.search(pattern, text)
            if match:
                count = int(match.group(1))
                indicators['estimated_employees'] = count
                break
        
        # Office locations
        location_keywords = ['office', 'location', 'headquarters', 'based in']
        for keyword in location_keywords:
            if keyword in text:
                indicators['has_multiple_locations'] = 'multiple' in text or 'offices' in text
                break
        
        return indicators
    
    def extract_contact_info(self, soup: BeautifulSoup) -> Dict:
        """Extract contact information"""
        contact = {}
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, soup.get_text())
        if emails:
            contact['emails'] = list(set(emails))
        
        # Phone patterns
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, soup.get_text())
        if phones:
            contact['phones'] = list(set(phones))
        
        # Social media links
        social_links = {}
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            if 'linkedin.com' in href:
                social_links['linkedin'] = link['href']
            elif 'twitter.com' in href:
                social_links['twitter'] = link['href']
            elif 'github.com' in href:
                social_links['github'] = link['href']
        
        if social_links:
            contact['social_media'] = social_links
        
        return contact
    
    async def analyze_social_presence(self, company_name: str) -> Dict:
        """Analyze company's social media presence"""
        # This would integrate with social media APIs
        # For now, return placeholder data
        return {
            'social_presence_score': 0.7,  # Placeholder
            'has_linkedin': True,
            'has_twitter': True,
            'estimated_followers': 1000
        }
    
    def analyze_job_postings(self, company: Company) -> Dict:
        """Analyze company's job posting patterns"""
        active_jobs = [job for job in company.jobs if job.is_active]
        
        if not active_jobs:
            return {}
        
        analysis = {}
        
        # Job posting frequency
        recent_jobs = [
            job for job in active_jobs 
            if job.created_at >= datetime.utcnow() - timedelta(days=30)
        ]
        analysis['monthly_job_postings'] = len(recent_jobs)
        
        # Experience level distribution
        exp_levels = {}
        for job in active_jobs:
            level = job.experience_level or 'unknown'
            exp_levels[level] = exp_levels.get(level, 0) + 1
        analysis['experience_level_distribution'] = exp_levels
        
        # Remote work policy
        remote_jobs = [job for job in active_jobs if job.remote_option == 'remote']
        hybrid_jobs = [job for job in active_jobs if job.remote_option == 'hybrid']
        
        total_jobs = len(active_jobs)
        analysis['remote_work_percentage'] = (len(remote_jobs) / total_jobs * 100) if total_jobs > 0 else 0
        analysis['hybrid_work_percentage'] = (len(hybrid_jobs) / total_jobs * 100) if total_jobs > 0 else 0
        
        # Salary analysis
        salaries = [job.salary_min for job in active_jobs if job.salary_min]
        if salaries:
            analysis['avg_min_salary'] = sum(salaries) / len(salaries)
            analysis['salary_range_min'] = min(salaries)
            analysis['salary_range_max'] = max(salaries)
        
        # Skills demand
        all_skills = []
        for job in active_jobs:
            if job.required_skills:
                skills = [skill.strip().lower() for skill in job.required_skills.split(',')]
                all_skills.extend(skills)
        
        skill_counts = {}
        for skill in all_skills:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        # Top 10 most demanded skills
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        analysis['top_skills_demand'] = dict(top_skills)
        
        return analysis
    
    async def llm_company_analysis(self, company: Company, existing_intel: Dict) -> Dict:
        """Use LLM to analyze company and provide insights"""
        try:
            prompt = f"""
            Analyze the following company and provide intelligence insights:
            
            Company: {company.name}
            Website: {company.website or 'Not available'}
            Industry: {company.industry or 'Not specified'}
            Location: {company.location or 'Not specified'}
            Description: {company.description or 'Not available'}
            
            Existing Intelligence:
            {existing_intel}
            
            Please provide a JSON response with the following analysis:
            1. company_category: startup/scale-up/enterprise/government
            2. growth_stage: early/growth/mature/declining
            3. innovation_score: 0-1 (how innovative the company appears)
            4. work_culture_score: 0-1 (how good the work culture seems)
            5. stability_score: 0-1 (how stable the company appears)
            6. career_growth_potential: 0-1 (potential for career growth)
            7. key_strengths: list of 3-5 key strengths
            8. potential_concerns: list of potential concerns
            9. ideal_candidate_profile: description of ideal candidate
            10. market_position: strong/moderate/weak
            
            Respond only with valid JSON.
            """
            
            response = await self.llm_client.get_completion(prompt)
            
            # Parse JSON response
            import json
            try:
                llm_analysis = json.loads(response)
                return llm_analysis
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in LLM company analysis: {e}")
            return {}
    
    def calculate_company_score(self, company: Company, intelligence: Dict) -> float:
        """Calculate overall company score based on various factors"""
        score = 0.0
        max_score = 1.0
        
        # Base score from existing data
        if company.description:
            score += 0.1
        if company.website:
            score += 0.1
        if company.industry:
            score += 0.05
        if company.location:
            score += 0.05
        
        # Job posting activity (0-0.2)
        job_intel = intelligence.get('monthly_job_postings', 0)
        if job_intel > 0:
            job_score = min(job_intel / 10, 1.0) * 0.2  # Normalize to 0-0.2
            score += job_score
        
        # Technology stack (0-0.1)
        tech_stack = intelligence.get('detected_tech_stack', [])
        if tech_stack:
            tech_score = min(len(tech_stack) / 10, 1.0) * 0.1
            score += tech_score
        
        # Social presence (0-0.1)
        social_score = intelligence.get('social_presence_score', 0) * 0.1
        score += social_score
        
        # LLM analysis scores (0-0.4)
        llm_scores = [
            intelligence.get('innovation_score', 0),
            intelligence.get('work_culture_score', 0),
            intelligence.get('stability_score', 0),
            intelligence.get('career_growth_potential', 0)
        ]
        
        if any(llm_scores):
            avg_llm_score = sum(llm_scores) / len([s for s in llm_scores if s > 0])
            score += avg_llm_score * 0.4
        
        # Remote work friendliness (0-0.1)
        remote_percentage = intelligence.get('remote_work_percentage', 0)
        if remote_percentage > 0:
            remote_score = (remote_percentage / 100) * 0.1
            score += remote_score
        
        return min(score, max_score)
    
    def update_company_metadata(self, db: Session, company: Company, 
                               intelligence: Dict, score: float):
        """Update company with intelligence metadata"""
        # Update basic fields
        if intelligence.get('web_description') and not company.description:
            company.description = intelligence['web_description']
        
        # Update tech stack
        if intelligence.get('detected_tech_stack'):
            existing_tech = company.tech_stack.split(',') if company.tech_stack else []
            new_tech = intelligence['detected_tech_stack']
            combined_tech = list(set(existing_tech + new_tech))
            company.tech_stack = ','.join(combined_tech)
        
        # Update company category and size
        if intelligence.get('company_category'):
            if intelligence['company_category'] in ['startup', 'scale-up']:
                company.company_size = 'startup'
            elif intelligence['company_category'] == 'enterprise':
                company.company_size = 'large'
            else:
                company.company_size = 'medium'
        
        # Update estimated employee count
        if intelligence.get('size_indicators', {}).get('estimated_employees'):
            emp_count = intelligence['size_indicators']['estimated_employees']
            if emp_count < 50:
                company.company_size = 'startup'
            elif emp_count < 500:
                company.company_size = 'medium'
            else:
                company.company_size = 'large'
        
        # Update funding stage based on growth stage
        growth_stage = intelligence.get('growth_stage')
        if growth_stage == 'early':
            company.funding_stage = 'seed'
        elif growth_stage == 'growth':
            company.funding_stage = 'series_a'
        elif growth_stage == 'mature':
            company.funding_stage = 'series_c'
        
        # Update company score
        company.company_score = score
        
        # Update intelligence timestamp
        company.intelligence_updated_at = datetime.utcnow()
        
        # Store raw intelligence data (if you have a JSON field)
        # company.intelligence_data = json.dumps(intelligence)
    
    async def batch_analyze_companies(self, limit: int = 10) -> List[Dict]:
        """Analyze multiple companies in batch"""
        db = SessionLocal()
        try:
            # Get companies that need analysis
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            companies = db.query(Company).filter(
                or_(
                    Company.intelligence_updated_at.is_(None),
                    Company.intelligence_updated_at < cutoff_date
                )
            ).limit(limit).all()
            
            results = []
            for company in companies:
                try:
                    result = await self.analyze_company(company.id)
                    results.append(result)
                    
                    # Add delay to avoid rate limiting
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error analyzing company {company.id}: {e}")
                    continue
            
            return results
            
        finally:
            db.close()
    
    def get_company_intelligence_summary(self, company_id: int) -> Dict:
        """Get intelligence summary for a company"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                return {}
            
            return {
                "company_id": company_id,
                "name": company.name,
                "score": company.company_score,
                "last_analyzed": company.intelligence_updated_at,
                "tech_stack": company.tech_stack.split(',') if company.tech_stack else [],
                "company_size": company.company_size,
                "funding_stage": company.funding_stage,
                "active_jobs": len([j for j in company.jobs if j.is_active])
            }
            
        finally:
            db.close()

# Global analyzer instance
company_analyzer = CompanyAnalyzer()
