# src/aggregation/indeed_scraper.py
import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote_plus
import aiohttp
from bs4 import BeautifulSoup

from ..config import config

logger = logging.getLogger(__name__)

class IndeedScraper:
    """Indeed job board scraper"""
    
    def __init__(self):
        self.base_url = "https://www.indeed.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = None
    
    async def search_jobs(self, keyword: str, location: str = "", limit: int = 50) -> List[Dict]:
        """Search jobs on Indeed"""
        jobs = []
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Build search URL
            params = {
                'q': keyword,
                'l': location,
                'limit': min(limit, 50),  # Indeed limits results per page
                'sort': 'date'  # Sort by date to get newest jobs
            }
            
            search_url = f"{self.base_url}/jobs?" + urlencode(params)
            logger.info(f"Searching Indeed: {search_url}")
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    logger.error(f"Indeed search failed with status {response.status}")
                    return jobs
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find job cards
                job_cards = soup.find_all('div', {'data-jk': True}) or soup.find_all('a', {'data-jk': True})
                
                for card in job_cards[:limit]:
                    try:
                        job_data = await self.extract_job_data(card, soup)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error extracting job data: {e}")
                        continue
                
                logger.info(f"Found {len(jobs)} jobs on Indeed for '{keyword}' in '{location}'")
                
        except Exception as e:
            logger.error(f"Error searching Indeed: {e}")
        
        return jobs
    
    async def extract_job_data(self, job_card, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract job data from Indeed job card"""
        try:
            job_data = {}
            
            # Job ID
            job_id = job_card.get('data-jk')
            if not job_id:
                return None
            
            job_data['external_id'] = job_id
            job_data['source'] = 'Indeed'
            
            # Job title
            title_elem = job_card.find('h2', class_='jobTitle') or job_card.find('a', {'data-jk': job_id})
            if title_elem:
                title_link = title_elem.find('a') or title_elem
                job_data['title'] = title_link.get_text(strip=True) if title_link else None
                
                # Job URL
                if title_link and title_link.get('href'):
                    job_data['apply_url'] = self.base_url + title_link['href']
            
            # Company name
            company_elem = job_card.find('span', class_='companyName') or job_card.find('a', {'data-testid': 'company-name'})
            if company_elem:
                company_link = company_elem.find('a') or company_elem
                job_data['company_name'] = company_link.get_text(strip=True)
            
            # Location
            location_elem = job_card.find('div', {'data-testid': 'job-location'}) or job_card.find('div', class_='companyLocation')
            if location_elem:
                job_data['location'] = location_elem.get_text(strip=True)
            
            # Salary
            salary_elem = job_card.find('span', class_='salaryText') or job_card.find('div', {'data-testid': 'attribute_snippet_testid'})
            if salary_elem:
                salary_text = salary_elem.get_text(strip=True)
                salary_range = self.parse_salary(salary_text)
                if salary_range:
                    job_data.update(salary_range)
            
            # Job summary/description snippet
            summary_elem = job_card.find('div', class_='job-snippet') or job_card.find('div', {'data-testid': 'job-snippet'})
            if summary_elem:
                job_data['description'] = summary_elem.get_text(strip=True)
            
            # Job type and remote indicators
            job_type_elem = job_card.find('div', class_='attribute_snippet')
            if job_type_elem:
                job_type_text = job_type_elem.get_text(strip=True).lower()
                
                if 'remote' in job_type_text:
                    job_data['remote_option'] = 'remote'
                elif 'hybrid' in job_type_text:
                    job_data['remote_option'] = 'hybrid'
                else:
                    job_data['remote_option'] = 'onsite'
                
                if 'full-time' in job_type_text or 'full time' in job_type_text:
                    job_data['job_type'] = 'full_time'
                elif 'part-time' in job_type_text or 'part time' in job_type_text:
                    job_data['job_type'] = 'part_time'
                elif 'contract' in job_type_text:
                    job_data['job_type'] = 'contract'
                elif 'internship' in job_type_text:
                    job_data['job_type'] = 'internship'
            
            # Posted date
            date_elem = job_card.find('span', class_='date')
            if date_elem:
                job_data['posted_date'] = date_elem.get_text(strip=True)
            
            # Only return if we have essential data
            if job_data.get('title') and job_data.get('company_name'):
                return job_data
            
        except Exception as e:
            logger.error(f"Error extracting job data from Indeed card: {e}")
        
        return None
    
    def parse_salary(self, salary_text: str) -> Optional[Dict]:
        """Parse salary information from text"""
        if not salary_text:
            return None
        
        salary_text = salary_text.replace(',', '').replace('$', '')
        
        # Pattern for salary ranges like "50000 - 80000" or "50K - 80K"
        range_pattern = r'(\d+)(?:k|K)?\s*[-–]\s*(\d+)(?:k|K)?'
        range_match = re.search(range_pattern, salary_text)
        
        if range_match:
            min_sal = int(range_match.group(1))
            max_sal = int(range_match.group(2))
            
            # Convert K to thousands
            if 'k' in salary_text.lower():
                min_sal *= 1000
                max_sal *= 1000
            
            return {
                'salary_min': min_sal,
                'salary_max': max_sal
            }
        
        # Pattern for single salary like "75000" or "75K"
        single_pattern = r'(\d+)(?:k|K)?'
        single_match = re.search(single_pattern, salary_text)
        
        if single_match:
            salary = int(single_match.group(1))
            if 'k' in salary_text.lower():
                salary *= 1000
            
            # If it says "up to" it's a max, otherwise treat as minimum
            if 'up to' in salary_text.lower():
                return {'salary_max': salary}
            else:
                return {'salary_min': salary}
        
        return None
    
    async def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get detailed job information from job page"""
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
                desc_elem = soup.find('div', {'id': 'jobDescriptionText'}) or soup.find('div', class_='jobsearch-jobDescriptionText')
                if desc_elem:
                    details['description'] = desc_elem.get_text(strip=True)
                
                # Company information
                company_section = soup.find('div', {'data-testid': 'inlineHeader-companyName'})
                if company_section:
                    company_link = company_section.find('a')
                    if company_link:
                        details['company_website'] = self.base_url + company_link.get('href', '')
                
                # Benefits
                benefits_section = soup.find('div', {'data-testid': 'benefits'})
                if benefits_section:
                    benefits_text = benefits_section.get_text(strip=True)
                    details['benefits'] = benefits_text
                
                # Skills/qualifications
                qualifications = soup.find('div', string=re.compile('Qualifications|Requirements|Skills'))
                if qualifications:
                    qual_parent = qualifications.find_parent()
                    if qual_parent:
                        skills_text = qual_parent.get_text(strip=True)
                        # Extract common skills
                        skills = self.extract_skills_from_text(skills_text)
                        if skills:
                            details['required_skills'] = ', '.join(skills)
                
                return details
                
        except Exception as e:
            logger.error(f"Error getting job details from {job_url}: {e}")
        
        return None
    
    def extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skills from job description text"""
        common_skills = [
            'python', 'java', 'javascript', 'react', 'angular', 'vue',
            'node.js', 'express', 'django', 'flask', 'spring', 'sql',
            'mysql', 'postgresql', 'mongodb', 'redis', 'aws', 'azure',
            'docker', 'kubernetes', 'git', 'linux', 'agile', 'scrum',
            'machine learning', 'data science', 'tensorflow', 'pytorch',
            'html', 'css', 'typescript', 'c++', 'c#', 'go', 'rust'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in common_skills:
            if skill in text_lower:
                found_skills.append(skill)
        
        return found_skills[:10]  # Limit to top 10 skills
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
