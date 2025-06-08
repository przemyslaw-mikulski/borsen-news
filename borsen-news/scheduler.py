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
                # Add translation column (using 'none' for scheduled fetches)
                articles_df["translated_summary"] = articles_df["summary"].apply(
                    lambda x: translate_text(x, "none")
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
            # Schedule fetch every 30 minutes between 6am and 8pm CET
            # This will run at: 6:00, 6:30, 7:00, 7:30, ... 19:30, 20:00
            self.scheduler.add_job(
                self.fetch_articles_job,
                'cron',
                hour='6-20',
                minute='0,30',
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
        
        # Calculate next scheduled run (every 30 minutes from 6am to 8pm CET)
        # Valid times: 6:00, 6:30, 7:00, 7:30, ..., 19:30, 20:00
        
        # Check if we're within the active hours (6am to 8pm)
        current_hour = now_cet.hour
        current_minute = now_cet.minute
        
        if 6 <= current_hour <= 20:
            # We're in the active period, find next 30-minute slot
            if current_minute < 30:
                # Next run is at :30 of current hour
                next_run = now_cet.replace(minute=30, second=0, microsecond=0)
            elif current_hour < 20:
                # Next run is at :00 of next hour
                next_run = now_cet.replace(hour=current_hour + 1, minute=0, second=0, microsecond=0)
            else:
                # We're past 20:30, next run is tomorrow at 6:00
                next_run = (now_cet + timedelta(days=1)).replace(
                    hour=6, minute=0, second=0, microsecond=0
                )
        else:
            # We're outside active hours, next run is at 6:00 today or tomorrow
            if current_hour < 6:
                # Before 6am today, next run is at 6:00 today
                next_run = now_cet.replace(hour=6, minute=0, second=0, microsecond=0)
            else:
                # After 8pm today, next run is at 6:00 tomorrow
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
