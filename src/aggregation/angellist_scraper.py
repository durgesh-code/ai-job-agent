# src/aggregation/angellist_scraper.py
import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote_plus
import aiohttp
from bs4 import BeautifulSoup

from ..config import config

logger = logging.getLogger(__name__)

class AngelListScraper:
    """AngelList (Wellfound) job board scraper for startup jobs"""
    
    def __init__(self):
        self.base_url = "https://wellfound.com"  # AngelList rebranded to Wellfound
        self.api_key = config.api_keys.get("angellist_api_key")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive'
        }
        self.session = None
    
    async def search_jobs(self, keyword: str, location: str = "", limit: int = 50) -> List[Dict]:
        """Search jobs on AngelList/Wellfound"""
        jobs = []
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Build search URL
            params = {
                'role': keyword,
                'location': location,
                'remote': 'true',  # Include remote jobs
                'experience': 'any'
            }
            
            search_url = f"{self.base_url}/jobs?" + urlencode(params)
            logger.info(f"Searching AngelList: {search_url}")
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    logger.error(f"AngelList search failed with status {response.status}")
                    return jobs
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find job cards (AngelList structure)
                job_cards = soup.find_all('div', class_='job-card') or soup.find_all('div', {'data-test': 'JobCard'})
                
                for card in job_cards[:limit]:
                    try:
                        job_data = await self.extract_job_data(card)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error extracting AngelList job data: {e}")
                        continue
                
                logger.info(f"Found {len(jobs)} jobs on AngelList for '{keyword}' in '{location}'")
                
        except Exception as e:
            logger.error(f"Error searching AngelList: {e}")
        
        return jobs
    
    async def extract_job_data(self, job_card) -> Optional[Dict]:
        """Extract job data from AngelList job card"""
        try:
            job_data = {}
            job_data['source'] = 'AngelList'
            
            # Job title
            title_elem = job_card.find('h2') or job_card.find('a', class_='job-title')
            if title_elem:
                title_link = title_elem.find('a') or title_elem
                if title_link:
                    job_data['title'] = title_link.get_text(strip=True)
                    if title_link.get('href'):
                        job_data['apply_url'] = self.base_url + title_link['href']
            
            # Company name
            company_elem = job_card.find('div', class_='company-name') or job_card.find('a', class_='startup-link')
            if company_elem:
                company_link = company_elem.find('a') or company_elem
                if company_link:
                    job_data['company_name'] = company_link.get_text(strip=True)
                    if company_link.get('href'):
                        job_data['company_angellist'] = self.base_url + company_link['href']
            
            # Location and remote info
            location_elem = job_card.find('div', class_='location') or job_card.find('span', class_='job-location')
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                if 'remote' in location_text.lower():
                    job_data['remote_option'] = 'remote'
                    job_data['location'] = 'Remote'
                else:
                    job_data['location'] = location_text
                    job_data['remote_option'] = 'onsite'
            
            # Salary range
            salary_elem = job_card.find('div', class_='salary') or job_card.find('span', class_='compensation')
            if salary_elem:
                salary_text = salary_elem.get_text(strip=True)
                salary_range = self.parse_salary(salary_text)
                if salary_range:
                    job_data.update(salary_range)
            
            # Equity information
            equity_elem = job_card.find('div', class_='equity') or job_card.find('span', class_='equity-range')
            if equity_elem:
                equity_text = equity_elem.get_text(strip=True)
                job_data['equity_range'] = equity_text
            
            # Job description snippet
            desc_elem = job_card.find('div', class_='job-description') or job_card.find('p', class_='description')
            if desc_elem:
                job_data['description'] = desc_elem.get_text(strip=True)
            
            # Experience level
            exp_elem = job_card.find('div', class_='experience') or job_card.find('span', class_='experience-level')
            if exp_elem:
                exp_text = exp_elem.get_text(strip=True).lower()
                job_data['experience_level'] = self.map_experience_level(exp_text)
            
            # Skills/tags
            skills_container = job_card.find('div', class_='tags') or job_card.find('div', class_='skills')
            if skills_container:
                skill_tags = skills_container.find_all('span', class_='tag') or skills_container.find_all('a')
                skills = [tag.get_text(strip=True) for tag in skill_tags]
                if skills:
                    job_data['required_skills'] = ', '.join(skills[:10])  # Limit to 10 skills
            
            # Company stage/size (startup specific)
            stage_elem = job_card.find('div', class_='company-stage') or job_card.find('span', class_='stage')
            if stage_elem:
                stage_text = stage_elem.get_text(strip=True)
                job_data['company_stage'] = stage_text
                job_data['company_size'] = self.map_company_stage_to_size(stage_text)
            
            # Job type (usually full-time for startups)
            job_data['job_type'] = 'full_time'
            
            # Extract job ID from URL or data attributes
            if job_data.get('apply_url'):
                job_id_match = re.search(r'/jobs/(\d+)', job_data['apply_url'])
                if job_id_match:
                    job_data['external_id'] = job_id_match.group(1)
            
            # Only return if we have essential data
            if job_data.get('title') and job_data.get('company_name'):
                return job_data
            
        except Exception as e:
            logger.error(f"Error extracting AngelList job data: {e}")
        
        return None
    
    def parse_salary(self, salary_text: str) -> Optional[Dict]:
        """Parse salary information from AngelList text"""
        if not salary_text:
            return None
        
        salary_text = salary_text.replace(',', '').replace('$', '').replace('k', '000').replace('K', '000')
        
        # Pattern for salary ranges like "$50000 - $80000" or "$50K - $80K"
        range_pattern = r'(\d+)(?:000)?\s*[-–]\s*(\d+)(?:000)?'
        range_match = re.search(range_pattern, salary_text)
        
        if range_match:
            min_sal = int(range_match.group(1))
            max_sal = int(range_match.group(2))
            
            # Adjust if values are too small (likely in K format)
            if min_sal < 1000:
                min_sal *= 1000
                max_sal *= 1000
            
            return {
                'salary_min': min_sal,
                'salary_max': max_sal
            }
        
        # Pattern for single salary
        single_pattern = r'(\d+)(?:000)?'
        single_match = re.search(single_pattern, salary_text)
        
        if single_match:
            salary = int(single_match.group(1))
            if salary < 1000:
                salary *= 1000
            
            return {'salary_min': salary}
        
        return None
    
    def map_experience_level(self, exp_text: str) -> str:
        """Map AngelList experience level to our standard levels"""
        exp_text = exp_text.lower()
        
        if any(word in exp_text for word in ['junior', 'entry', 'intern', 'graduate']):
            return 'entry'
        elif any(word in exp_text for word in ['senior', 'lead', 'principal', 'staff']):
            return 'senior'
        elif any(word in exp_text for word in ['mid', 'intermediate', '2-5', '3-7']):
            return 'mid'
        elif any(word in exp_text for word in ['director', 'vp', 'head', 'chief']):
            return 'lead'
        else:
            return 'mid'  # Default
    
    def map_company_stage_to_size(self, stage: str) -> str:
        """Map company stage to size category"""
        stage_lower = stage.lower()
        
        if any(word in stage_lower for word in ['seed', 'pre-seed', 'idea', 'early']):
            return 'startup'
        elif any(word in stage_lower for word in ['series a', 'series b', 'growth']):
            return 'medium'
        elif any(word in stage_lower for word in ['series c', 'series d', 'late', 'public']):
            return 'large'
        else:
            return 'startup'  # Default for AngelList
    
    async def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get detailed job information from AngelList job page"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            
            async with self.session.get(job_url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                details = {}
                
                # Full job description
                desc_elem = soup.find('div', class_='job-description-full') or soup.find('div', class_='description')
                if desc_elem:
                    details['description'] = desc_elem.get_text(strip=True)
                
                # Company information
                company_section = soup.find('div', class_='company-info')
                if company_section:
                    # Company description
                    company_desc = company_section.find('div', class_='company-description')
                    if company_desc:
                        details['company_description'] = company_desc.get_text(strip=True)
                    
                    # Company size
                    size_elem = company_section.find('div', class_='company-size')
                    if size_elem:
                        details['company_size'] = size_elem.get_text(strip=True)
                    
                    # Funding info
                    funding_elem = company_section.find('div', class_='funding')
                    if funding_elem:
                        details['company_funding'] = funding_elem.get_text(strip=True)
                
                # Benefits and perks
                benefits_section = soup.find('div', class_='benefits') or soup.find('div', class_='perks')
                if benefits_section:
                    benefits_list = benefits_section.find_all('li') or benefits_section.find_all('div', class_='benefit')
                    if benefits_list:
                        benefits = [benefit.get_text(strip=True) for benefit in benefits_list]
                        details['benefits'] = '\n'.join(benefits)
                
                # Requirements/qualifications
                req_section = soup.find('div', class_='requirements') or soup.find('div', class_='qualifications')
                if req_section:
                    req_text = req_section.get_text(strip=True)
                    skills = self.extract_skills_from_text(req_text)
                    if skills:
                        details['required_skills'] = ', '.join(skills)
                
                return details
                
        except Exception as e:
            logger.error(f"Error getting AngelList job details: {e}")
        
        return None
    
    def extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skills from job description text"""
        startup_skills = [
            'python', 'javascript', 'react', 'node.js', 'aws', 'docker',
            'kubernetes', 'mongodb', 'postgresql', 'redis', 'graphql',
            'typescript', 'go', 'rust', 'machine learning', 'ai',
            'blockchain', 'web3', 'solidity', 'ethereum', 'defi',
            'product management', 'growth hacking', 'analytics',
            'a/b testing', 'user research', 'design thinking',
            'agile', 'scrum', 'lean startup', 'mvp'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in startup_skills:
            if skill in text_lower:
                found_skills.append(skill)
        
        return found_skills[:10]  # Limit to top 10 skills
    
    async def get_trending_startup_jobs(self, limit: int = 50) -> List[Dict]:
        """Get trending jobs from high-growth startups"""
        trending_keywords = [
            'software engineer', 'full stack developer', 'product manager',
            'data scientist', 'growth manager', 'frontend engineer',
            'backend engineer', 'devops engineer', 'machine learning engineer'
        ]
        
        all_jobs = []
        for keyword in trending_keywords:
            jobs = await self.search_jobs(keyword, limit=limit//len(trending_keywords))
            all_jobs.extend(jobs)
        
        return all_jobs
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
