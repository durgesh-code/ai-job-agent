# src/aggregation/linkedin_scraper.py
import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote_plus
import aiohttp
from bs4 import BeautifulSoup

from ..config import config

logger = logging.getLogger(__name__)

class LinkedInScraper:
    """LinkedIn job board scraper (requires API access or careful scraping)"""
    
    def __init__(self):
        self.base_url = "https://www.linkedin.com"
        self.api_key = config.api_keys.get("linkedin_api_key")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive'
        }
        self.session = None
    
    async def search_jobs(self, keyword: str, location: str = "", limit: int = 50) -> List[Dict]:
        """Search jobs on LinkedIn"""
        jobs = []
        
        try:
            # If API key is available, use LinkedIn API
            if self.api_key:
                jobs = await self.search_jobs_api(keyword, location, limit)
            else:
                # Fallback to web scraping (limited and may break)
                logger.warning("LinkedIn API key not configured, using limited web scraping")
                jobs = await self.search_jobs_web(keyword, location, limit)
            
            logger.info(f"Found {len(jobs)} jobs on LinkedIn for '{keyword}' in '{location}'")
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {e}")
        
        return jobs
    
    async def search_jobs_api(self, keyword: str, location: str, limit: int) -> List[Dict]:
        """Search jobs using LinkedIn API (requires partner access)"""
        # Note: LinkedIn's official API requires partner access
        # This is a placeholder for the API implementation
        logger.warning("LinkedIn API integration requires partner access - not implemented")
        return []
    
    async def search_jobs_web(self, keyword: str, location: str, limit: int) -> List[Dict]:
        """Search jobs via web scraping (limited functionality)"""
        jobs = []
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Build search URL for LinkedIn jobs
            params = {
                'keywords': keyword,
                'location': location,
                'f_TPR': 'r86400',  # Last 24 hours
                'f_JT': 'F',  # Full-time
                'sortBy': 'DD'  # Sort by date
            }
            
            search_url = f"{self.base_url}/jobs/search?" + urlencode(params)
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    logger.error(f"LinkedIn search failed with status {response.status}")
                    return jobs
                
                html = await response.text()
                
                # Check if we're blocked or redirected to login
                if 'authwall' in html or 'login' in response.url.path:
                    logger.warning("LinkedIn requires authentication - cannot scrape jobs")
                    return jobs
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find job cards (LinkedIn structure changes frequently)
                job_cards = soup.find_all('div', {'data-entity-urn': True}) or soup.find_all('li', class_='result-card')
                
                for card in job_cards[:limit]:
                    try:
                        job_data = await self.extract_job_data_web(card)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error extracting LinkedIn job data: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error in LinkedIn web scraping: {e}")
        
        return jobs
    
    async def extract_job_data_web(self, job_card) -> Optional[Dict]:
        """Extract job data from LinkedIn job card (web scraping)"""
        try:
            job_data = {}
            job_data['source'] = 'LinkedIn'
            
            # Job title
            title_elem = job_card.find('h3') or job_card.find('a', class_='result-card__full-card-link')
            if title_elem:
                title_link = title_elem.find('a') or title_elem
                if title_link:
                    job_data['title'] = title_link.get_text(strip=True)
                    if title_link.get('href'):
                        job_data['apply_url'] = self.base_url + title_link['href']
            
            # Company name
            company_elem = job_card.find('h4') or job_card.find('a', class_='result-card__subtitle-link')
            if company_elem:
                company_link = company_elem.find('a') or company_elem
                if company_link:
                    job_data['company_name'] = company_link.get_text(strip=True)
            
            # Location
            location_elem = job_card.find('span', class_='job-result-card__location')
            if location_elem:
                job_data['location'] = location_elem.get_text(strip=True)
            
            # Job description snippet
            desc_elem = job_card.find('p', class_='job-result-card__snippet')
            if desc_elem:
                job_data['description'] = desc_elem.get_text(strip=True)
            
            # Posted time
            time_elem = job_card.find('time')
            if time_elem:
                job_data['posted_date'] = time_elem.get_text(strip=True)
            
            # Extract job ID from data attributes
            entity_urn = job_card.get('data-entity-urn')
            if entity_urn:
                job_id = entity_urn.split(':')[-1]
                job_data['external_id'] = job_id
            
            # Only return if we have essential data
            if job_data.get('title') and job_data.get('company_name'):
                return job_data
            
        except Exception as e:
            logger.error(f"Error extracting LinkedIn job data: {e}")
        
        return None
    
    async def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get detailed job information from LinkedIn job page"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            
            async with self.session.get(job_url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                
                # Check for authentication wall
                if 'authwall' in html or 'login' in response.url.path:
                    logger.warning("LinkedIn job details require authentication")
                    return None
                
                soup = BeautifulSoup(html, 'html.parser')
                
                details = {}
                
                # Full job description
                desc_elem = soup.find('div', class_='description__text')
                if desc_elem:
                    details['description'] = desc_elem.get_text(strip=True)
                
                # Company information
                company_elem = soup.find('a', class_='topcard__org-name-link')
                if company_elem:
                    details['company_name'] = company_elem.get_text(strip=True)
                    if company_elem.get('href'):
                        details['company_linkedin'] = self.base_url + company_elem['href']
                
                # Job criteria (experience level, job type, etc.)
                criteria_section = soup.find('ul', class_='description__job-criteria-list')
                if criteria_section:
                    criteria_items = criteria_section.find_all('li')
                    for item in criteria_items:
                        label_elem = item.find('h3')
                        value_elem = item.find('span')
                        
                        if label_elem and value_elem:
                            label = label_elem.get_text(strip=True).lower()
                            value = value_elem.get_text(strip=True)
                            
                            if 'seniority level' in label:
                                details['experience_level'] = self.map_seniority_level(value)
                            elif 'employment type' in label:
                                details['job_type'] = self.map_employment_type(value)
                            elif 'industries' in label:
                                details['company_industry'] = value
                
                # Skills from job description
                if details.get('description'):
                    skills = self.extract_skills_from_text(details['description'])
                    if skills:
                        details['required_skills'] = ', '.join(skills)
                
                return details
                
        except Exception as e:
            logger.error(f"Error getting LinkedIn job details: {e}")
        
        return None
    
    def map_seniority_level(self, linkedin_level: str) -> str:
        """Map LinkedIn seniority level to our standard levels"""
        level_map = {
            'internship': 'entry',
            'entry level': 'entry',
            'associate': 'entry',
            'mid-senior level': 'mid',
            'senior level': 'senior',
            'director': 'lead',
            'executive': 'lead'
        }
        
        return level_map.get(linkedin_level.lower(), 'mid')
    
    def map_employment_type(self, linkedin_type: str) -> str:
        """Map LinkedIn employment type to our standard types"""
        type_map = {
            'full-time': 'full_time',
            'part-time': 'part_time',
            'contract': 'contract',
            'temporary': 'contract',
            'internship': 'internship',
            'volunteer': 'volunteer'
        }
        
        return type_map.get(linkedin_type.lower(), 'full_time')
    
    def extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skills from job description text"""
        common_skills = [
            'python', 'java', 'javascript', 'react', 'angular', 'vue',
            'node.js', 'express', 'django', 'flask', 'spring', 'sql',
            'mysql', 'postgresql', 'mongodb', 'redis', 'aws', 'azure',
            'docker', 'kubernetes', 'git', 'linux', 'agile', 'scrum',
            'machine learning', 'data science', 'tensorflow', 'pytorch',
            'html', 'css', 'typescript', 'c++', 'c#', 'go', 'rust',
            'project management', 'leadership', 'communication'
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
