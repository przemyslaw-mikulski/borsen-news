import time
import threading
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from fetch_and_translate import fetch_articles, translate_text
from db import save_to_db

# Set up CET timezone
CET = pytz.timezone('Europe/Vienna')  # CET timezone


class ArticleScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=CET)
        self.is_running = False
        self.last_fetch_time = None
        self.last_fetch_status = "Not started"
        self.fetch_count = 0
        
    def fetch_articles_job(self):
        """Job function to fetch and save articles"""
        try:
            print("🕐 Scheduled fetch starting...")
            
            # Fetch articles
            articles_df = fetch_articles()
            
            if len(articles_df) > 0:
                # Add translation column (using automatic translation for scheduled fetches)
                articles_df["translated_summary"] = articles_df["summary"].apply(
                    lambda x: translate_text(x, "togetherai")
                )
                
                # Save to database
                deleted_count, skipped_count, added_count = save_to_db(articles_df)
                
                self.last_fetch_time = datetime.now(CET).strftime(
                    "%Y-%m-%d %H:%M:%S CET"
                )
                self.last_fetch_status = (
                    f"✅ Success: Added {added_count}, Skipped {skipped_count}"
                )
                self.fetch_count += 1
                
                print(f"🤖 Automatic fetch completed: {self.last_fetch_status}")
                
            else:
                self.last_fetch_time = datetime.now(CET).strftime(
                    "%Y-%m-%d %H:%M:%S CET"
                )
                self.last_fetch_status = "⚠️ No articles found"
                print("🤖 Automatic fetch: No new articles found")
                
        except Exception as e:
            self.last_fetch_time = datetime.now(CET).strftime(
                "%Y-%m-%d %H:%M:%S CET"
            )
            self.last_fetch_status = f"❌ Error: {str(e)}"
            print(f"🤖 Automatic fetch failed: {str(e)}")
    
    def start_scheduler(self):
        """Start the scheduler"""
        if not self.is_running:
            # Schedule fetch every 2 hours between 6am and 12pm CET
            # This will run at: 6:00, 8:00, 10:00, 12:00
            self.scheduler.add_job(
                self.fetch_articles_job,
                'cron',
                hour='6,8,10,12',
                minute='0',
                id='frequent_fetch'
            )
            self.scheduler.start()
            self.is_running = True
            return True
        return False
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
        
    def get_status(self):
        """Get current scheduler status"""
        now_cet = datetime.now(CET)
        next_run = None
        
        # Calculate next scheduled run (every 2 hours from 6am to 12pm CET)
        # Valid times: 6:00, 8:00, 10:00, 12:00
        
        # Check if we're within the active hours (6am to 12pm)
        current_hour = now_cet.hour
        current_minute = now_cet.minute
        
        # Define the valid run hours
        valid_hours = [6, 8, 10, 12]
        
        if 6 <= current_hour <= 12:
            # We're in the active period, find next 2-hour slot
            next_hour = None
            for hour in valid_hours:
                if hour > current_hour or (hour == current_hour and current_minute < 0):
                    next_hour = hour
                    break
            
            if next_hour:
                # Next run is at next_hour:00 today
                next_run = now_cet.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            else:
                # We're past 12:00, next run is tomorrow at 6:00
                next_run = (now_cet + timedelta(days=1)).replace(
                    hour=6, minute=0, second=0, microsecond=0
                )
        else:
            # We're outside active hours, next run is at 6:00 today or tomorrow
            if current_hour < 6:
                # Before 6am today, next run is at 6:00 today
                next_run = now_cet.replace(hour=6, minute=0, second=0, microsecond=0)
            else:
                # After 12pm today, next run is at 6:00 tomorrow
                next_run = (now_cet + timedelta(days=1)).replace(
                    hour=6, minute=0, second=0, microsecond=0
                )
            
        return {
            "is_running": self.is_running,
            "last_fetch_time": self.last_fetch_time,
            "last_fetch_status": self.last_fetch_status,
            "next_run": (
                next_run.strftime("%Y-%m-%d %H:%M:%S CET") 
                if next_run else None
            ),
            "fetch_count": self.fetch_count,
            "current_time": now_cet.strftime("%Y-%m-%d %H:%M:%S CET")
        }


# Global scheduler instance
_scheduler_instance = None


def get_scheduler():
    """Get the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ArticleScheduler()
    return _scheduler_instance
