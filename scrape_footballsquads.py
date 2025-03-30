import requests
from bs4 import BeautifulSoup
import csv
import os
from urllib.parse import urljoin, urlparse
import time # Added for delay
import re # Need re for main function regex

BASE_URL = "https://www.footballsquads.co.uk"
ARCHIVE_URL = "https://www.footballsquads.co.uk/archive.htm"
NUM_PLAYER_DATA_COLS = 15 # Define how many player columns we expect in CSV

# --- Map country names to expected part of flag image source URL ---
# (Based on common patterns and the example `images/flags/europe/eng.gif`)
COUNTRY_FLAG_MAP = {
    "eng.gif": "England",
    "esp.gif": "Spain",
    "ita.gif": "Italy",
    "ger.gif": "Germany",
    "fra.gif": "France",
    "por.gif": "Portugal",
    "ned.gif": "Netherlands", # Assuming ned for Netherlands
    "bel.gif": "Belgium",
    "sco.gif": "Scotland",    # Assuming sco for Scotland
    # Add more mappings if needed by inspecting flag image URLs
}

def get_soup(url):
    """
    Given a URL, return a BeautifulSoup object of its HTML content.
    Includes a small delay.
    """
    try:
        print(f"Fetching: {url}") # Add print statement to see progress
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1) # Small delay to be polite
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None # Return None if fetching fails

def is_valid_link(href):
    """
    Basic check to ensure the link is not empty, not a mailto, and not JavaScript-based.
    """
    if not href:
        return False
    if href.startswith("mailto:") or href.startswith("javascript:"):
        return False
    # Add check to avoid linking back to the main archive page from itself
    if "archive.htm" in href.lower():
        return False
    return True

def scrape_team_roster(team_url, country, season, league, writer):
    """
    Given the URL of a team's squad page, scrape the roster table using
    the logic adapted from the user's example, and write to the main CSV writer.
    """
    soup = get_soup(team_url)
    if not soup: return # Skip if fetching failed

    # --- New Table Finding Logic (adapted from user's example) ---
    roster_table = None
    tables_found = soup.find_all("table")
    print(f"  - Checking {len(tables_found)} tables found on: {team_url}")

    for candidate_table in tables_found:
        # Look for <th> elements first for headers
        headers_th = candidate_table.find_all("th")
        headers = [th.get_text(strip=True).lower() for th in headers_th]

        # Fallback: If no <th>, check the first row's <td> elements
        if not headers:
             first_row = candidate_table.find("tr")
             if first_row:
                 headers_td = first_row.find_all("td")
                 headers = [td.get_text(strip=True).lower() for td in headers_td]

        print(f"    - Checking Table Headers: {headers}") # Diagnostic print

        # Check for key headers identified in the user's example script
        has_number = any("number" in h or "#" == h for h in headers) # Allow "number" or just "#"
        has_name = any("name" in h for h in headers)
        has_pos = any("pos" in h for h in headers)

        if has_number and has_name and has_pos:
            roster_table = candidate_table
            print(f"  - Identified potential roster table based on key headers ('number', 'name', 'pos') on: {team_url}")
            break # Assume first match is the correct one

    if not roster_table:
        print(f"  - Could not identify roster table using key header check on: {team_url}")
        return

    # --- Data Extraction (adapted) ---
    rows = roster_table.find_all("tr")
    if not rows:
        print(f"  - Roster table found, but it contains no rows: {team_url}")
        return

    # Determine where data rows start (skip header row(s))
    # A simple approach: skip the first row if it contained the headers we matched.
    # More robustly: Skip rows until we find one with typical data cells (<td>).
    start_row_index = 0
    for idx, row in enumerate(rows):
         # Check if the row contains <td> cells, assuming headers were <th> or first row <td>
         # Also check if it doesn't look exactly like the header row we found
         td_cells = row.find_all("td")
         # Extract text to compare with headers list (handle th/td mix in header row)
         current_row_texts = [cell.get_text(strip=True).lower() for cell in row.find_all(['th', 'td'])]

         if td_cells and current_row_texts != headers: # Check for data cells AND that it's not the header row itself
             start_row_index = idx
             break
    
    # If we couldn't find a definite start, but headers were found, assume header was row 0
    if start_row_index == 0 and headers and len(rows) > 1:
        print("    - Assuming header was row 0, starting data extraction from row 1.")
        start_row_index = 1
    elif start_row_index == 0 and len(rows) <=1 :
         print(f"    - Table has header but no data rows found: {team_url}")
         return # No data rows to process


    print(f"  - Extracting player data starting from row index {start_row_index}")
    players_extracted = 0
    for row in rows[start_row_index:]:
        # Get text from both <td> and <th> (player number might be in <th>)
        cols = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]

        # Basic validity check (e.g., must have at least 2 columns like Number and Name)
        if len(cols) >= 2 and any(c for c in cols): # Ensure at least 2 cols and not all empty
            # --- Pad or truncate player data to fit NUM_PLAYER_DATA_COLS ---
            player_data = cols[:NUM_PLAYER_DATA_COLS] # Take up to N columns
            # Pad with empty strings if fewer than N columns were extracted
            player_data.extend([''] * (NUM_PLAYER_DATA_COLS - len(player_data)))

            # Construct the full data row including metadata
            data_row = [country, season, league, team_url] + player_data
            writer.writerow(data_row)
            players_extracted += 1
        # else: # Optional: Log skipped rows
            # print(f"    - Skipping row with insufficient data: {cols}")

    print(f"  - Extracted {players_extracted} players from: {team_url}")

def scrape_league_page(league_url, country, season, league, writer):
    """
    Scrape a single league page to find all teams, then scrape each team roster.
    """
    soup = get_soup(league_url)
    if not soup: return # Skip if fetching failed

    print(f"Scraping League Page: {league_url} ({country}/{season}/{league})")
    # Find links that likely lead to team pages within the main content area
    main_div = soup.find('div', id='main')
    if not main_div:
         print(f"  - No 'main' div found on league page: {league_url}")
         main_div = soup # Fallback to searching the whole page

    team_links_found = 0
    for a_tag in main_div.find_all("a", href=True):
        href = a_tag["href"]
        # Check if it looks like a team page link (ends in .htm, not index/main page)
        if is_valid_link(href) and href.lower().endswith(".htm") and not any(x in href.lower() for x in ['index', 'default', 'main']):
            # Construct full link to the team page
            team_page_url = urljoin(league_url, href)
            # Basic check to ensure we're not looping back to the league page itself
            if urlparse(team_page_url).path != urlparse(league_url).path:
                 team_links_found += 1
                 scrape_team_roster(team_page_url, country, season, league, writer)

    if team_links_found == 0:
        print(f"  - No team links found on league page: {league_url}")


def main():
    output_filename = "footballsquads_archive.csv"
    try:
        with open(output_filename, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # --- Define Header ---
            header = ["Country", "Season", "LeagueName", "TeamURL"]
            # Add generic player data column headers
            header.extend([f"PlayerData_{i+1}" for i in range(NUM_PLAYER_DATA_COLS)])
            writer.writerow(header)

            archive_soup = get_soup(ARCHIVE_URL)
            if not archive_soup:
                print("Failed to fetch archive page. Exiting.")
                return

            processed_leagues = set() # Keep track of processed league URLs to avoid duplicates

            print("\nStarting link extraction from archive page...")
            # Find links within the main content for better targeting
            main_div = archive_soup.find('div', id='main')
            if not main_div:
                 print("Could not find main div on archive page, searching whole page.")
                 main_div = archive_soup # Fallback

            for a_tag in main_div.find_all("a", href=True):
                href = a_tag["href"]
                link_text = a_tag.get_text(strip=True)

                # Focus on links likely to be league/season pages based on path structure
                if is_valid_link(href) and href.lower().endswith(".htm"):
                    full_link = urljoin(BASE_URL, href)

                    # Avoid processing the same league URL multiple times
                    if full_link in processed_leagues:
                        continue

                    # Parse metadata from URL path
                    parsed_path = urlparse(full_link).path
                    path_parts = parsed_path.strip("/").split("/")

                    # Expecting structure like: /country/season/league/page.htm
                    # Or sometimes /country/league/page.htm (if season implicit)
                    if len(path_parts) >= 3:
                        country_guess = path_parts[0]
                        # Try to identify season vs league based on common patterns
                        part1 = path_parts[1]
                        part2 = path_parts[2]

                        # Simple heuristic: if part1 looks like YYYY-YYYY or YYYY, assume it's season
                        if re.match(r"^\d{4}(-\d{4})?$", part1):
                            season_guess = part1
                            league_guess = part2
                        # Maybe the season is implicit in the page itself?
                        # Fallback if structure is different
                        else:
                             season_guess = link_text # Or extract from page title later
                             league_guess = part1 # Assume part1 is league if not season format


                        print(f"\nFound potential league link: {full_link}")
                        print(f"  -> Guessed Metadata: Country={country_guess}, Season={season_guess}, League={league_guess}")

                        # Scrape the identified league page
                        scrape_league_page(full_link, country_guess, season_guess, league_guess, writer)
                        processed_leagues.add(full_link) # Mark as processed

                    else:
                         print(f"Skipping link with unexpected path structure: {full_link}")


    except IOError as e:
        print(f"Error writing to CSV file {output_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print(f"\nScraping attempt complete. Data saved to {output_filename}")

if __name__ == "__main__":
    main() 