#!/usr/bin/env python3
"""
Backup Script for Users and Assignments
Creates backups of users and assignments before cleanup (optional safety measure)
"""

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

def json_serializer(obj):
    """JSON serializer for MongoDB ObjectId and datetime objects"""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return str(obj)

async def backup_preserved_data():
    """Create backups of users and assignments collections"""
    
    logger.info("💾 Starting backup of users and assignments...")
    
    try:
        from app.database.connection import get_database
        
        # Get database connection
        db = await get_database()
        logger.info("✅ Database connection established")
        
        # Create backup directory
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        collections_to_backup = ['users', 'assignments']
        
        for collection_name in collections_to_backup:
            logger.info(f"💾 Backing up {collection_name} collection...")
            
            # Check if collection exists
            collections = await db.list_collection_names()
            if collection_name not in collections:
                logger.warning(f"⚠️  Collection {collection_name} does not exist - skipping")
                continue
            
            # Get all documents
            documents = await db[collection_name].find({}).to_list(None)
            
            if not documents:
                logger.info(f"📭 Collection {collection_name} is empty - creating empty backup")
                documents = []
            
            # Create backup file
            backup_file = backup_dir / f"{collection_name}_backup_{timestamp}.json"
            
            # Convert ObjectIds and dates to strings for JSON serialization
            serializable_docs = []
            for doc in documents:
                # Convert _id to string
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                
                # Convert datetime objects
                for key, value in doc.items():
                    if hasattr(value, 'isoformat'):
                        doc[key] = value.isoformat()
                
                serializable_docs.append(doc)
            
            # Write to file
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'collection': collection_name,
                    'backup_date': datetime.now().isoformat(),
                    'document_count': len(serializable_docs),
                    'documents': serializable_docs
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Backed up {len(documents)} documents from {collection_name} to {backup_file}")
        
        logger.info("💾 Backup completed successfully!")
        logger.info(f"📁 Backups saved in: {backup_dir.absolute()}")
        
        return backup_dir
        
    except Exception as e:
        logger.error(f"💥 Backup failed: {e}")
        raise

async def restore_from_backup():
    """Restore users and assignments from backup (if needed)"""
    
    logger.info("🔄 Starting restore from backup...")
    
    try:
        from app.database.connection import get_database
        
        # Get database connection
        db = await get_database()
        
        backup_dir = Path("backups")
        if not backup_dir.exists():
            logger.error("❌ No backup directory found")
            return
        
        # Find latest backup files
        backup_files = {
            'users': None,
            'assignments': None
        }
        
        for collection_name in backup_files.keys():
            pattern = f"{collection_name}_backup_*.json"
            files = list(backup_dir.glob(pattern))
            
            if files:
                # Get the most recent backup
                latest_file = max(files, key=lambda x: x.stat().st_mtime)
                backup_files[collection_name] = latest_file
                logger.info(f"📁 Found backup for {collection_name}: {latest_file}")
            else:
                logger.warning(f"⚠️  No backup found for {collection_name}")
        
        # Restore collections
        for collection_name, backup_file in backup_files.items():
            if backup_file is None:
                continue
            
            logger.info(f"🔄 Restoring {collection_name} from {backup_file}...")
            
            # Read backup file
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            documents = backup_data.get('documents', [])
            
            if not documents:
                logger.info(f"📭 No documents to restore for {collection_name}")
                continue
            
            # Convert string IDs back to ObjectIds and restore dates
            from bson import ObjectId
            for doc in documents:
                if '_id' in doc and isinstance(doc['_id'], str):
                    try:
                        doc['_id'] = ObjectId(doc['_id'])
                    except:
                        # If invalid ObjectId, let MongoDB generate a new one
                        del doc['_id']
                
                # Convert ISO date strings back to datetime objects
                for key, value in doc.items():
                    if isinstance(value, str) and 'T' in value and value.endswith('Z'):
                        try:
                            doc[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            pass  # Keep as string if conversion fails
            
            # Clear existing collection and insert backup data
            await db[collection_name].delete_many({})
            
            if documents:
                result = await db[collection_name].insert_many(documents)
                logger.info(f"✅ Restored {len(result.inserted_ids)} documents to {collection_name}")
            else:
                logger.info(f"📭 No documents to insert for {collection_name}")
        
        logger.info("🔄 Restore completed successfully!")
        
    except Exception as e:
        logger.error(f"💥 Restore failed: {e}")
        raise

async def main():
    """Main function"""
    print("💾 Backup and Restore Utility")
    print("="*40)
    print("1. Create backup")
    print("2. Restore from backup")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    try:
        if choice == '1':
            backup_dir = await backup_preserved_data()
            print(f"\n✅ Backup completed successfully!")
            print(f"📁 Backups saved in: {backup_dir.absolute()}")
            
        elif choice == '2':
            await restore_from_backup()
            print(f"\n✅ Restore completed successfully!")
            
        elif choice == '3':
            print("👋 Goodbye!")
            
        else:
            print("❌ Invalid choice")
            
    except Exception as e:
        print(f"\n💥 Operation failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())