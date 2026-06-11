"""Browser agent that collects hiring data from LinkedIn and Naukri."""
import asyncio
from layer1_agents.browser_agents.playwright_scraper import linkedin_search_jobs, naukri_search_jobs


async def collect_hiring(company_name: str) -> str:
    """Collect job listings from LinkedIn and Naukri for hiring signals.

    Searches both platforms for jobs at the company and extracts job titles,
    departments, and locations. Returns plain text list of opportunities.

    Errors are caught and an empty string is returned on failure.
    """
    try:
        # Search both platforms in parallel
        linkedin_jobs, naukri_jobs = await asyncio.gather(
            linkedin_search_jobs(company_name),
            naukri_search_jobs(company_name),
            return_exceptions=True
        )

        # Combine results
        combined = ""
        if linkedin_jobs and not isinstance(linkedin_jobs, Exception):
            combined += f"LinkedIn Jobs:\n{linkedin_jobs}\n\n"
        if naukri_jobs and not isinstance(naukri_jobs, Exception):
            combined += f"Naukri Jobs:\n{naukri_jobs}"

        return combined
    except Exception as e:
        print(f"hiring_agent error: {e}")
        return ""
