import os
import glob
from utils import logger, load_config, DATA_DIR

def clean_redundant_caches():
    config = load_config()
    
    # Gather all configured topics
    active_topics = set()
    for key in ["projects", "yad2Projects", "madlanProjects", "facebookProjects"]:
        for p in config.get(key, []):
            if "topic" in p and p["topic"]:
                active_topics.add(p["topic"])
                
    # Find all json files in DATA_DIR recursively
    json_files = glob.glob(os.path.join(DATA_DIR, "**/*.json"), recursive=True)
    
    removed_any = False
    for file_path in json_files:
        rel_path = os.path.relpath(file_path, DATA_DIR)
        topic = os.path.splitext(rel_path)[0]
        topic = topic.replace(os.sep, "/") # Normalize path separators
        
        if topic not in active_topics:
            logger.info(f"Removing redundant cache file: {file_path}")
            os.remove(file_path)
            
            # Remove empty parent directories if any
            parent_dir = os.path.dirname(file_path)
            if parent_dir != DATA_DIR and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
                
            removed_any = True
            
    if removed_any:
        # Signal GitHub action to push changes
        with open(os.path.join(os.path.dirname(__file__), "push_me"), "w") as f:
            f.write("")

if __name__ == "__main__":
    clean_redundant_caches()
