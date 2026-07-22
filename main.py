import os
import sys
import pandas as pd
from scraper import GitHubScraper

def main():
    print("=" * 60)
    print("           GitHub User Profile Data Scraper")
    print("=" * 60)

    # Step 1: Prompt search query
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Using search query from command line: {query}")
    else:
        query = input("Enter GitHub search query: ").strip()

    if not query:
        print("[!] No search query provided. Exiting.")
        sys.exit(1)

    print(f"\n[+] Searching GitHub for query: '{query}'...")
    
    # Step 2: Initialize scraper & run
    scraper = GitHubScraper(headless=True)
    results = scraper.scrape(query, max_results=10)

    if not results:
        print("[-] No profiles extracted.")
        return

    # Step 3: Format extracted data into pandas DataFrame
    df = pd.DataFrame(results)
    
    # Ensure column ordering matches specified requirement:
    # Name | Email | LinkedIn URL | GitHub URL | Repositories
    desired_columns = ["Name", "Email", "LinkedIn URL", "GitHub URL", "Repositories"]
    df = df.reindex(columns=desired_columns)

    print("\n" + "=" * 60)
    print("                    Extracted Results")
    print("=" * 60)
    print(df.to_string(index=False))
    print("=" * 60)

    # Step 4: Export results to CSV and Excel
    csv_file = "github_users.csv"
    excel_file = "github_users.xlsx"

    df.to_csv(csv_file, index=False)
    df.to_excel(excel_file, index=False, engine='openpyxl')

    print(f"\n[+] Data successfully exported to:")
    print(f"    - CSV:   {os.path.abspath(csv_file)}")
    print(f"    - Excel: {os.path.abspath(excel_file)}")

if __name__ == "__main__":
    main()
