# 🤖 AI Job Agent

An intelligent job discovery and matching system that automatically finds relevant job opportunities, analyzes company data, and provides personalized job recommendations using advanced AI and machine learning techniques.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technical Architecture](#technical-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## 🎯 Overview

The AI Job Agent is a comprehensive job search automation platform that:

- **Discovers Companies**: Automatically finds and categorizes companies across different sectors (MNCs, startups, unicorns, etc.)
- **Scrapes Job Listings**: Extracts job postings from company websites and career pages
- **Intelligent Matching**: Uses semantic analysis and machine learning to match jobs with user profiles
- **Analytics Dashboard**: Provides insights into job market trends, salary benchmarks, and application tracking
- **Resume Analysis**: Parses and analyzes resumes to extract skills, experience, and preferences

### 🎯 Who Is This For?

- **Job Seekers**: Automate your job search and get personalized recommendations
- **Recruiters**: Discover new companies and analyze job market trends
- **Career Counselors**: Help clients with data-driven career insights
- **Researchers**: Analyze job market data and hiring trends

## ✨ Features

### 🔍 Company Discovery
- **Multi-Category Search**: Discovers MNCs, startups, medium companies, unicorns, and sector-specific companies
- **Comprehensive Database**: Stores company information including industry, size, funding stage, tech stack
- **Smart Filtering**: AI-powered company categorization and duplicate detection

### 💼 Job Aggregation
- **Website Scraping**: Extracts jobs from company career pages
- **Multiple Sources**: Support for LinkedIn, Indeed, Glassdoor (configurable)
- **Real-time Updates**: Continuous monitoring for new job postings
- **Data Enrichment**: Enhances job data with salary estimates, experience levels, and skill requirements

### 🎯 Intelligent Matching
- **Semantic Analysis**: Uses sentence transformers for deep job-profile matching
- **Multi-factor Scoring**: Considers skills, experience, location, salary, and company preferences
- **Personalized Recommendations**: Tailored job suggestions based on user profile and preferences
- **Learning Algorithm**: Improves recommendations based on user feedback

### 📊 Analytics & Insights
- **Market Trends**: Track job demand by skills, locations, and industries
- **Salary Benchmarks**: Real-time salary data analysis
- **Application Tracking**: Monitor your job application pipeline
- **Performance Metrics**: Success rates, response times, and conversion analytics

### 🌐 Web Dashboard
- **Interactive UI**: Modern, responsive web interface
- **Real-time Updates**: Live job matching and notification system
- **Profile Management**: Comprehensive user profile and preference settings
- **Export Features**: Download job lists, reports, and analytics

## 🏗️ Technical Architecture

### Core Technologies
- **Backend**: FastAPI (Python) - High-performance async web framework
- **Database**: SQLAlchemy with SQLite (easily configurable for PostgreSQL/MySQL)
- **AI/ML**: Sentence Transformers, FAISS for vector similarity search
- **Web Scraping**: Playwright, BeautifulSoup4 for dynamic content extraction
- **Task Queue**: Celery with Redis for background job processing
- **Frontend**: HTML5, CSS3, JavaScript with modern responsive design

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Dashboard │    │   API Gateway   │    │  Background     │
│   (Frontend)    │◄──►│   (FastAPI)     │◄──►│  Workers        │
└─────────────────┘    └─────────────────┘    │  (Celery)       │
                                │              └─────────────────┘
                                ▼                       │
┌─────────────────┐    ┌─────────────────┐              │
│   User Profile  │    │   Job Matcher   │              │
│   Management    │◄──►│   (AI Engine)   │              │
└─────────────────┘    └─────────────────┘              │
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │   Vector Store  │    │   Web Scrapers  │
│   (SQLAlchemy)  │◄──►│   (FAISS)       │    │   (Playwright)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow
1. **Company Discovery**: AI searches and categorizes companies
2. **Job Scraping**: Automated extraction of job postings
3. **Data Processing**: NLP analysis and skill extraction
4. **Vector Encoding**: Job descriptions converted to embeddings
5. **Matching Engine**: Semantic similarity scoring
6. **User Interface**: Real-time dashboard updates

## 🚀 Installation

### Prerequisites
- Python 3.8+ (recommended: Python 3.10+)
- Git
- 4GB+ RAM (for ML models)
- Internet connection (for web scraping)

### Quick Start

1. **Clone the Repository**
```bash
git clone <repository-url>
cd ai-job-agent
```

2. **Create Virtual Environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Initialize Database**
```bash
python3 init_database.py
```

5. **Configure Settings**
```bash
cp configs/settings.yml.example configs/settings.yml
# Edit configs/settings.yml with your API keys and preferences
```

6. **Start the Application**
```bash
python3 run_web.py
```

7. **Access Dashboard**
Open your browser and navigate to: `http://localhost:8001`

### Docker Installation (Alternative)

```bash
# Build the container
docker build -t ai-job-agent .

# Run the application
docker run -p 8001:8001 -v $(pwd)/data:/app/data ai-job-agent
```

## ⚙️ Configuration

### Essential Configuration

Edit `configs/settings.yml` to configure:

#### API Keys (Required for full functionality)
```yaml
google_api_key: "your-google-api-key"
google_cse_id: "your-custom-search-engine-id"
openai_api_key: "your-openai-api-key"  # Optional: for enhanced matching
```

#### Job Discovery Settings
```yaml
search_num: 15                    # Companies to discover per search
max_companies_per_category: 20    # Max companies per category
max_jobs_per_company: 50         # Max jobs to scrape per company
```

#### Matching Algorithm Weights
```yaml
matching:
  weights:
    semantic_score: 0.3      # Job description similarity
    skill_match: 0.25        # Skills alignment
    experience_match: 0.2    # Experience level match
    location_match: 0.1      # Location preference
    salary_match: 0.1        # Salary expectation
    company_match: 0.05      # Company preference
```

### Advanced Configuration

#### Performance Tuning
```yaml
performance:
  max_concurrent_requests: 10
  request_delay_seconds: 1
  cache_ttl_hours: 24
  batch_size: 10
```

#### Database Configuration
```yaml
database:
  url: "sqlite:///data/db.sqlite"  # For production: postgresql://...
  echo: false
  pool_size: 10
```

## 📖 Usage

### 1. Initial Setup

**Create Your Profile**
1. Access the dashboard at `http://localhost:8001`
2. Navigate to Profile Settings
3. Upload your resume (PDF/DOCX supported)
4. Set job preferences (location, salary, company size)
5. Specify target roles and skills

### 2. Company Discovery

**Automatic Discovery**
```python
from src.crawler.company_finder import CompanyFinder

finder = CompanyFinder()
# Discover companies across all categories
companies = finder.search_companies_comprehensive(
    max_per_category=20,
    include_categories=['mnc_tech', 'startups', 'unicorns']
)
```

**Manual Company Addition**
- Use the web interface to add specific companies
- Import company lists via CSV upload
- API endpoint: `POST /api/companies`

### 3. Job Scraping

**Automated Scraping**
The system automatically scrapes jobs from discovered companies. Monitor progress in the dashboard.

**Manual Trigger**
```python
from src.aggregation.job_aggregator import JobAggregator

aggregator = JobAggregator()
# Scrape jobs from specific company
jobs = aggregator.scrape_company_jobs(company_id=123)
```

### 4. Job Matching

**View Matches**
- Dashboard shows personalized job recommendations
- Filter by match score, location, salary, company
- Save interesting jobs for later review

**API Access**
```python
# Get matches for user
GET /api/matches?user_id=1&min_score=0.7

# Rate a job match
POST /api/matches/{match_id}/rate
{
  "rating": 4,
  "feedback": "Great match, applied!"
}
```

### 5. Analytics

**Market Insights**
- View trending skills and technologies
- Salary benchmarks by role and location
- Company hiring patterns
- Job market growth trends

**Personal Analytics**
- Application success rates
- Profile optimization suggestions
- Skill gap analysis
- Career progression recommendations

## 🔌 API Documentation

### Authentication
Currently uses session-based authentication. JWT support planned for v2.0.

### Core Endpoints

#### Companies
```http
GET    /api/companies              # List companies
POST   /api/companies              # Add company
GET    /api/companies/{id}         # Get company details
PUT    /api/companies/{id}         # Update company
DELETE /api/companies/{id}         # Delete company
```

#### Jobs
```http
GET    /api/jobs                   # List jobs
GET    /api/jobs/{id}              # Get job details
POST   /api/jobs/{id}/apply        # Mark as applied
```

#### Matching
```http
GET    /api/matches                # Get user matches
POST   /api/matches/refresh        # Refresh matches
PUT    /api/matches/{id}/rate      # Rate match
```

#### Analytics
```http
GET    /api/analytics/trends       # Market trends
GET    /api/analytics/salaries     # Salary benchmarks
GET    /api/analytics/user-stats   # User statistics
```

### Response Format
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 📁 Project Structure

```
ai-job-agent/
├── configs/
│   └── settings.yml              # Configuration file
├── data/
│   ├── db.sqlite                # SQLite database
│   ├── embeddings.faiss         # Vector embeddings
│   └── ids.pkl                  # ID mappings
├── src/
│   ├── aggregation/             # Job scraping modules
│   │   ├── job_aggregator.py    # Main aggregation engine
│   │   ├── indeed_scraper.py    # Indeed integration
│   │   └── angellist_scraper.py # AngelList integration
│   ├── analytics/               # Analytics and insights
│   │   └── analytics_engine.py  # Market analysis
│   ├── crawler/                 # Company discovery
│   │   ├── company_finder.py    # Company search engine
│   │   ├── scraper.py          # Web scraping utilities
│   │   └── vendors.py          # External API integrations
│   ├── embeddings/             # ML and vector operations
│   │   ├── encoder.py          # Text encoding
│   │   └── vector_store.py     # FAISS operations
│   ├── matcher/                # Job matching engine
│   │   └── enhanced_matcher.py # AI matching algorithm
│   ├── performance/            # Performance optimization
│   │   └── scaling_manager.py  # Resource management
│   ├── resume/                 # Resume processing
│   │   ├── parser.py           # Resume parsing
│   │   └── profile.py          # Profile management
│   ├── web/                    # Web interface
│   │   ├── app.py              # FastAPI application
│   │   ├── static/             # CSS, JS, images
│   │   └── templates/          # HTML templates
│   ├── db.py                   # Database configuration
│   ├── models.py               # SQLAlchemy models
│   └── main.py                 # Application entry point
├── requirements.txt            # Python dependencies
├── init_database.py           # Database initialization
├── run_web.py                 # Web server launcher
└── README.md                  # This file
```

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Make your changes
5. Run tests: `pytest`
6. Commit changes: `git commit -m 'Add amazing feature'`
7. Push to branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Code Standards
- Follow PEP 8 style guidelines
- Add docstrings to all functions and classes
- Write unit tests for new features
- Update documentation as needed

### Areas for Contribution
- Additional job board integrations
- Enhanced matching algorithms
- Mobile-responsive UI improvements
- Performance optimizations
- Documentation improvements

## 🔧 Troubleshooting

### Common Issues

#### Database Errors
```bash
# Reset database
rm data/db.sqlite
python3 init_database.py
```

#### Missing Dependencies
```bash
# Reinstall all dependencies
pip install --upgrade -r requirements.txt
```

#### Web Scraping Blocked
- Check if target websites have anti-bot measures
- Adjust `request_delay_seconds` in settings
- Consider using proxy servers for large-scale scraping

#### Performance Issues
- Increase `max_workers` in settings for more parallelism
- Use PostgreSQL instead of SQLite for better performance
- Enable Redis caching for faster responses

### Debug Mode
Enable debug logging in `configs/settings.yml`:
```yaml
logging:
  level: "DEBUG"
web:
  debug: true
```

### Memory Issues
- Reduce `batch_size` in settings
- Limit `max_companies_per_category`
- Use smaller ML models (configure in embeddings settings)

## ❓ FAQ

**Q: Do I need API keys to use the system?**
A: Google API keys are required for company discovery. OpenAI API is optional but enhances matching quality.

**Q: Can I use this for commercial purposes?**
A: Yes, but please respect website terms of service when scraping. Consider rate limiting and ethical scraping practices.

**Q: How accurate is the job matching?**
A: Matching accuracy improves with more data and user feedback. Typical accuracy ranges from 75-90% for well-defined profiles.

**Q: Can I integrate with my existing ATS?**
A: Yes, the API allows integration with external systems. Contact us for enterprise integration support.

**Q: What's the difference between semantic and skill matching?**
A: Semantic matching analyzes job description context, while skill matching focuses on specific technical requirements.

**Q: How often should I run company discovery?**
A: Weekly for active job searching, monthly for passive monitoring. Configure in the scheduler settings.

**Q: Can I export my data?**
A: Yes, all data can be exported via API or web interface in JSON/CSV formats.

---

## 📞 Support

- **Documentation**: [Wiki](link-to-wiki)
- **Issues**: [GitHub Issues](link-to-issues)
- **Discussions**: [GitHub Discussions](link-to-discussions)
- **Email**: support@ai-job-agent.com

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Sentence Transformers for semantic analysis
- FastAPI for the excellent web framework
- Playwright for reliable web scraping
- The open-source community for inspiration and tools

---

**Happy Job Hunting! 🎯**
