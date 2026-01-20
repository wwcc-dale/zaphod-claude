import re
import os

def process_directory_sessions(directory="."):
    # Loop through every file in the provided directory
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            file_path = os.path.join(directory, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Split content by Session headers
            sessions = re.split(r'(?=# Session \d+)', content.strip())
            
            for session in sessions:
                if not session.strip():
                    continue
                    
                # Extract session title
                title_match = re.search(r'# (Session \d+.*)', session)
                if title_match:
                    raw_title = title_match.group(1).strip()
                    
                    # FILENAME ADJUSTMENT: Replace non-word chars/spaces with single hyphens
                    # This replaces any sequence of non-alphanumeric chars with a single '-'
                    clean_name = re.sub(r'[^\w]+', '-', raw_title).strip('-').lower()
                    output_filename = f"{clean_name}.md"
                    
                    # CONTENT ADJUSTMENT: Strip headers to leave only questions
                    cleaned_content = re.sub(r'^#+.*$', '', session, flags=re.MULTILINE).strip()
                    
                    with open(output_filename, 'w', encoding='utf-8') as output_file:
                        output_file.write(cleaned_content)
                    print(f"Source: {filename} -> Created: {output_filename}")

# Run the function in the current directory
if __name__ == "__main__":
    process_directory_sessions()
