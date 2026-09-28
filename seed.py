from sqlalchemy.orm import Session
from main import SessionLocal, GrievanceDB, Base, engine
from datetime import datetime, timedelta, timezone
import random
import uuid

def seed_data():
    db = SessionLocal()
    
    if db.query(GrievanceDB).count() > 0:
        print("Database already contains data. Skipping seed operation.")
        db.close()
        return

    sample_grievances = [
        {
            "citizen_name": "Rahul Sharma",
            "location": "Sector 4, Main Road",
            "raw_text": "Huge pothole causing traffic jams and minor accidents every day.",
            "category": "Road Infrastructure",
            "urgency_score": 4,
            "ai_summary": "A large pothole is causing daily traffic disruption and minor accidents.",
            "citizen_impact_count": 12,
            "status": "Resolution In Progress"
        },
        {
            "citizen_name": "Anita Desai",
            "location": "Green Park Layout",
            "raw_text": "Streetlights on 3rd cross have not been working for a week. Unsafe at night.",
            "category": "Electricity",
            "urgency_score": 3,
            "ai_summary": "Non-functional streetlights are creating a safety hazard for residents at night.",
            "citizen_impact_count": 5,
            "status": "Assigned to Ward Officer"
        },
        {
            "citizen_name": "Vikram Singh",
            "location": "Gandhi Nagar Water Tank",
            "raw_text": "Major water pipe burst, thousands of liters of clean water being wasted.",
            "category": "Water Supply",
            "urgency_score": 5,
            "ai_summary": "A burst water pipe is resulting in significant and ongoing water wastage.",
            "citizen_impact_count": 25,
            "status": "AI Verified"
        },
        {
            "citizen_name": "Kavita Joshi",
            "location": "Old City Center",
            "raw_text": "Open manhole on the footpath. Very dangerous for elderly people and kids.",
            "category": "Public Safety",
            "urgency_score": 5,
            "ai_summary": "An uncovered manhole on a busy footpath represents a critical safety hazard.",
            "citizen_impact_count": 8,
            "status": "Received"
        }
    ]

    print("Seeding database v2 with sample complaints...")
    for data in sample_grievances:
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        random_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        
        db_grievance = GrievanceDB(
            reference_id=str(uuid.uuid4())[:8].upper(),
            citizen_name=data["citizen_name"],
            location=data["location"],
            raw_text=data["raw_text"],
            category=data["category"],
            urgency_score=data["urgency_score"],
            ai_summary=data["ai_summary"],
            citizen_impact_count=data["citizen_impact_count"],
            status=data["status"],
            timestamp=random_time
        )
        db.add(db_grievance)
    
    db.commit()
    print(f"Successfully seeded {len(sample_grievances)} advanced grievances into the v2 database.")
    db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_data()
