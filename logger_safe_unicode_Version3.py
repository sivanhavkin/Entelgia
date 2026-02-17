import sys
import logging


def safe_log(logger_func, msg):
    # מנסה להדפיס Unicode, ואם נכשל - מחליף תווים חריגים
    try:
        logger_func(msg)
    except UnicodeEncodeError:
        safe_msg = (
            msg.replace("✓", "V").replace("🚨", "!!")
            # אפשר להרחיב עם עוד .replace לפי צורך
        )
        logger_func(safe_msg)


# דוגמה:
logger = logging.getLogger("entelgia")
logging.basicConfig(level=logging.INFO)

# שימוש:
safe_log(logger.info, "✓ Config validation tests passed")
safe_log(logger.warning, "🚨 INVALID SESSION SIGNATURE: test123")
