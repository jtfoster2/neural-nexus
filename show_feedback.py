## run python3 show_feedback.py to see analysis

from db import get_overall_feedback_summary, get_feedback_summary

# display system-wide feedback (all users)
print("System-wide feedback:", get_overall_feedback_summary())

# display feedback for a specific user
# user_email = "demo@example.com"  # change to a real email

user_email = "ploypawachot33@gmail.com" 

print(f"User feedback for {user_email}:", get_feedback_summary(user_email))