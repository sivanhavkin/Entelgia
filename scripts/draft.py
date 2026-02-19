import time
import random

class FixyRegulator:
    """סוכן העל שאחראי על יציבות המערכת והפעלת טריגרים של חלום"""
    def __init__(self, threshold=35.0):
        self.name = "Fixy"
        self.safety_threshold = threshold # סף בטיחות מעט גבוה מהרגיל

    def inspect_agent(self, target_agent):
        """בדיקה אם הסוכן יציב מספיק כדי להמשיך"""
        print(f"[{{self.name}}] Inspecting {{target_agent.name}}... Current Energy: {{target_agent.energy_level:.1f}}%")
        
        # אם האנרגיה נמוכה מדי, פיקסי כופה "שינה"
        if target_agent.energy_level <= self.safety_threshold:
            print(f"[{{self.name}}] WARNING: {{target_agent.name}} is unstable due to low energy. FORCING RECHARGE.")
            return True # טריגר לשינה כפויה
        
        # בדיקת עקביות (מוקסט כרנדומלי כרגע)
        if random.random() < 0.1 and target_agent.energy_level < 60:
            print(f"[{{self.name}}] Hallucination risk detected. Suspending dialogue for Dream Cycle.")
            return True
            
        return False

class EntelgiaAgent:
    def __init__(self, name, role):
        self.name = name
        self.role = role
        self.energy_level = 100.0
        self.conscious_memory = []
        self.subconscious_store = []
        self.regulator = FixyRegulator() # כל סוכן נמצא תחת פיקוח של פיקסי

    def process_step(self, input_text):
        # איבוד אנרגיה בסיסי על כל פעולה
        self.energy_level -= random.uniform(8, 15)
        self.conscious_memory.append(input_text)

        # פיקסי בודק את הסוכן
        should_recharge = self.regulator.inspect_agent(self)
        
        if should_recharge:
            self.dream_cycle()
            return "RECHARGED_AND_READY"
        
        return f"[{self.name}] Active and processing..."

    def dream_cycle(self):
        """תהליך עיבוד פנימי ושכחה"""
        print(f"\n--- STARTING DREAM CYCLE: {{self.name}} ---")
        
        # שלב השכחה: ניקוי קונטקסט ישן (Keep last 5)
        old_memories = len(self.conscious_memory)
        self.conscious_memory = self.conscious_memory[-5:]
        print(f"-> [Forgetting] Purged {{old_memories - 5}} irrelevant thoughts.")

        # שלב האינטגרציה: מעבר מהתת-מודע (מוקסט)
        print(f"-> [Integration] Moving deep insights to Conscious Layer.")
        
        # טעינת אנרגיה מלאה
        self.energy_level = 100.0
        print(f"--- {{self.name}} IS NOW FULLY RECHARGED ---\n")

# הרצה לדוגמה
socrates = EntelgiaAgent("Socrates", "Analytic")

for turn in range(1, 8):
    print(f"--- Turn {{turn}} ---")
    status = socrates.process_step("User query about ethics...")
    if status == "RECHARGED_AND_READY":
        print("System Note: Dialogue paused for internal consolidation.")
