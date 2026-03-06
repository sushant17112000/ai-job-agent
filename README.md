# Job Search Agent

An automated AWS Lambda-based job search agent that scrapes job listings from LinkedIn, Naukri.com, and IIMJobs.com, matches them against your resume, and delivers a daily CSV report to S3.

## Features

- **Multi-Portal Search**: Scrapes jobs from LinkedIn, Naukri.com, and IIMJobs.com
- **Smart Matching**: Matches jobs based on skills, job titles, experience, and location preferences
- **Automated Daily Reports**: Runs daily via EventBridge and saves results to S3
- **Customizable**: Configure resume data, matching criteria, and search parameters
- **Serverless**: Runs on AWS Lambda with no server management required

## Architecture

```
EventBridge (Daily Trigger)
        ↓
AWS Lambda Function
        ↓
[Scrape Jobs] → [Match Against Resume] → [Generate CSV]
        ↓
    S3 Bucket
```

## Project Structure

```
job-search-agent/
├── lambda_function.py          # Main Lambda handler
├── scrapers/
│   ├── __init__.py
│   ├── linkedin_scraper.py     # LinkedIn job scraper
│   ├── naukri_scraper.py       # Naukri.com scraper
│   └── iimjobs_scraper.py      # IIMJobs.com scraper
├── config.py                   # Resume data and configuration
├── job_matcher.py              # Job matching algorithm
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Prerequisites

- AWS Account (create at https://aws.amazon.com)
- Python 3.11+ (for local testing)
- AWS CLI (optional, for command-line deployment)

## Setup Instructions

### Step 1: Customize Resume Data

Edit `config.py` and update the `RESUME_DATA` dictionary with your information:

```python
RESUME_DATA = {
    "skills": ["Python", "AWS", "Machine Learning", ...],
    "desired_roles": ["Data Scientist", "ML Engineer", ...],
    "years_of_experience": 3,
    "locations": ["Bangalore", "Mumbai", "Remote"],
}
```

### Step 2: AWS Account Setup

#### 2.1 Create S3 Bucket

1. Go to AWS Console → S3
2. Click "Create bucket"
3. Bucket name: `job-search-results-{your-name}` (must be globally unique)
4. Region: Choose closest region (e.g., `us-east-1`, `ap-south-1`)
5. Keep default settings
6. Click "Create bucket"

#### 2.2 Create IAM Role for Lambda

1. Go to AWS Console → IAM → Roles
2. Click "Create role"
3. Select "AWS service" → "Lambda"
4. Attach these policies:
   - `AWSLambdaBasicExecutionRole` (for CloudWatch logs)
5. Click "Next"
6. Add inline policy for S3:
   - Click "Create policy"
   - Choose JSON tab and paste:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:PutObject"],
         "Resource": "arn:aws:s3:::job-search-results-{your-name}/*"
       }
     ]
   }
   ```
   - Name it: `S3JobUploadPolicy`
7. Name role: `JobSearchAgentLambdaRole`
8. Click "Create role"

#### 2.3 Create Lambda Function

1. Go to AWS Console → Lambda
2. Click "Create function"
3. Choose "Author from scratch"
4. Function name: `JobSearchAgent`
5. Runtime: **Python 3.11**
6. Architecture: **x86_64**
7. Execution role: Use existing role → `JobSearchAgentLambdaRole`
8. Click "Create function"

9. Configure Lambda settings:
   - Go to "Configuration" tab → "General configuration" → Edit
   - Timeout: **10 minutes** (600 seconds)
   - Memory: **512 MB**
   - Click "Save"

10. Add environment variable:
    - Go to "Configuration" tab → "Environment variables" → Edit
    - Add variable:
      - Key: `S3_BUCKET_NAME`
      - Value: `job-search-results-{your-name}`
    - Click "Save"

### Step 3: Package and Deploy

#### Option A: Manual Deployment (Recommended for Beginners)

1. **Install dependencies locally**:
   ```bash
   cd job-search-agent
   pip install -r requirements.txt -t ./package
   ```

2. **Copy source code to package**:
   ```bash
   # Windows PowerShell
   Copy-Item -Path *.py -Destination ./package/
   Copy-Item -Path scrapers -Destination ./package/ -Recurse

   # Linux/Mac
   cp -r *.py scrapers/ package/
   ```

3. **Create ZIP file**:
   ```bash
   # Windows PowerShell
   cd package
   Compress-Archive -Path * -DestinationPath ../job-search-agent.zip
   cd ..

   # Linux/Mac
   cd package
   zip -r ../job-search-agent.zip .
   cd ..
   ```

4. **Upload to Lambda**:
   - Go to Lambda console → JobSearchAgent
   - Click "Upload from" → ".zip file"
   - Select `job-search-agent.zip`
   - Click "Save"

#### Option B: AWS CLI Deployment

```bash
# Create deployment package
pip install -r requirements.txt -t ./package
cp -r *.py scrapers/ package/
cd package && zip -r ../job-search-agent.zip . && cd ..

# Upload to Lambda
aws lambda update-function-code \
  --function-name JobSearchAgent \
  --zip-file fileb://job-search-agent.zip
```

### Step 4: Set Up Daily Scheduling

1. Go to AWS Console → EventBridge → Rules
2. Click "Create rule"
3. Name: `DailyJobSearch`
4. Description: "Trigger job search agent daily"
5. Rule type: **Schedule**
6. Schedule pattern:
   - Choose "Cron-based schedule"
   - Cron expression: `0 9 * * ? *` (runs at 9 AM UTC daily)
   - Adjust time as needed (use https://crontab.guru for help)
7. Select target:
   - Target types: AWS service
   - Select a target: Lambda function
   - Function: `JobSearchAgent`
8. Click "Create"

### Step 5: Test the Function

1. Go to Lambda console → JobSearchAgent
2. Click "Test" tab
3. Create new test event:
   - Event name: `TestEvent`
   - Event JSON: `{}` (empty JSON object)
4. Click "Save"
5. Click "Test"
6. Check execution results in the output panel
7. View detailed logs in CloudWatch Logs

### Step 6: Check Results

1. Go to S3 console → your bucket
2. Look for file: `jobs_YYYY-MM-DD.csv`
3. Download and open in Excel/Google Sheets
4. Review matched jobs sorted by match score

## Usage

### Daily Automated Execution

Once deployed and scheduled, the agent will:
- Run automatically every day at the scheduled time
- Scrape jobs from all three portals
- Match jobs against your resume
- Generate a CSV report
- Upload to S3 with filename `jobs_YYYY-MM-DD.csv`

### Manual Execution

To run manually:
1. Go to Lambda console → JobSearchAgent
2. Click "Test"
3. Select your test event
4. Click "Test"

### Viewing Logs

Check CloudWatch Logs for execution details:
1. Go to CloudWatch → Log groups
2. Find log group: `/aws/lambda/JobSearchAgent`
3. View latest log stream for execution details

## Configuration

### Resume Data (`config.py`)

Customize your job search preferences:

```python
RESUME_DATA = {
    "skills": ["Python", "AWS", "Docker", ...],
    "desired_roles": ["Software Engineer", "DevOps Engineer", ...],
    "years_of_experience": 5,
    "locations": ["Bangalore", "Remote"],
}
```

### Matching Configuration

Adjust matching thresholds and weights:

```python
MATCHING_CONFIG = {
    "min_match_score": 40,  # Minimum score to include job (0-100)
    "experience_tolerance": 1,  # ±years for experience filter
    "weights": {
        "skills_match": 0.5,    # 50% weight on skills
        "title_match": 0.3,     # 30% weight on title
        "location_match": 0.2,  # 20% weight on location
    }
}
```

### Scraper Configuration

Adjust scraping behavior:

```python
SCRAPER_CONFIG = {
    "timeout": 10,           # Request timeout (seconds)
    "request_delay": 2,      # Delay between requests (seconds)
    "max_retries": 3,        # Max retries per request
}
```

## CSV Output Format

The generated CSV includes:
- **Title**: Job title
- **Company**: Company name
- **Location**: Job location
- **Experience**: Required experience
- **Match Score**: Relevance score (0-100%)
- **URL**: Link to apply
- **Source**: Job portal (LinkedIn/Naukri.com/IIMJobs.com)

Jobs are sorted by match score (highest first).

## Limitations

### LinkedIn
- Limited to ~10-25 public job listings without authentication
- May be blocked by anti-bot measures
- Consider using LinkedIn API or third-party services for better results

### Naukri.com & IIMJobs.com
- HTML structure may change, requiring scraper updates
- Rate limiting may apply
- Public listings only (no login)

### AWS Lambda
- 10-minute timeout (may not be enough for extensive scraping)
- Package size limit: 250 MB unzipped
- Consider using Lambda Layers for large dependencies

## Troubleshooting

### No jobs found
- Check CloudWatch logs for errors
- Verify resume data is configured correctly
- Test scrapers individually for issues
- Check if job portals blocked the requests

### Lambda timeout
- Reduce number of desired roles to search
- Increase Lambda timeout (max 15 minutes)
- Optimize scraper delays

### S3 upload failed
- Check IAM role permissions
- Verify S3 bucket name in environment variable
- Check S3 bucket exists and is accessible

### Package too large
- Use Lambda Layers for dependencies
- Remove unnecessary packages from requirements.txt

## Future Enhancements

- Add email delivery via SES
- Store job history in DynamoDB to avoid duplicates
- Add more job portals (Indeed, Glassdoor, AngelList)
- Implement ML-based job matching
- Create web dashboard for results
- Add notification on new high-match jobs

## Cost Estimate

AWS Free Tier eligible:
- Lambda: 1M requests/month free
- S3: 5 GB storage free
- EventBridge: Free

Estimated monthly cost (after free tier): **< $1**

## Security Notes

- Never commit credentials to version control
- Use IAM roles with least privilege
- Enable S3 encryption (already enabled in code)
- Regularly rotate API keys if using third-party services

## Support

For issues or questions:
1. Check CloudWatch logs first
2. Review this README
3. Check AWS Lambda documentation
4. Verify web scrapers are working (sites may change structure)

## License

This project is for personal use only. Respect the Terms of Service of job portals when scraping.

## Disclaimer

Web scraping may violate the Terms of Service of some websites. Use responsibly and consider using official APIs where available. This tool is provided as-is for educational purposes.
