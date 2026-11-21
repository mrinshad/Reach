"""
Script to enrich screening questions with options, add Race/Ethnicity,
and normalize post rejection reasons so they format cleanly for the screening modal.
"""
from src.db.connection import get_connection

def enrich_questions():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Add / Upsert Race/Ethnicity question with options
    race_options = [
        "Decline To Self Identify",
        "Asian",
        "White",
        "Black or African American",
        "Hispanic or Latino",
        "Two or More Races",
        "Native Hawaiian or Other Pacific Islander",
        "American Indian or Alaskan Native"
    ]
    cur.execute("""
        INSERT INTO screening_questions (
            id, question_key, question_text, category, answer, 
            is_standard, occurrences, sample_jobs, status, options, updated_at
        ) VALUES (
            'q_eeoc_race_indeed',
            'raceethnicity',
            'Race/Ethnicity',
            'demographic',
            'Asian',
            TRUE,
            1,
            ARRAY['Full Stack Engineer (Front-End) @ XO Health Inc.'],
            'ANSWERED',
            %s,
            NOW()
        )
        ON CONFLICT (question_key) DO UPDATE SET
            question_text = 'Race/Ethnicity',
            answer = 'Asian',
            options = %s,
            status = 'ANSWERED',
            updated_at = NOW()
    """, (race_options, race_options))
    print("✓ Added/Updated 'Race/Ethnicity' with options and answer 'Asian'")

    # 2. Update 'Have you worked with AWS Services - Lambda, S3, EC2, CloudWatch?'
    cur.execute("""
        UPDATE screening_questions
        SET answer = 'Yes',
            options = ARRAY['Yes', 'No'],
            status = 'ANSWERED',
            updated_at = NOW()
        WHERE question_key = 'haveyouworkedwithawsserviceslambdas3ec2cloudwatch'
    """)
    print("✓ Updated AWS Services answer to 'Yes' with options ['Yes', 'No']")

    # 3. Ensure Gender and Veteran Status have their full options array and clean text
    gender_options = ["Male", "Female", "Decline To Self Identify", "I don't wish to answer"]
    cur.execute("""
        UPDATE screening_questions
        SET options = %s,
            answer = 'Male',
            status = 'ANSWERED',
            updated_at = NOW()
        WHERE question_key = 'forgovernmentreportingpurposesweaskcandidatestorespondtothebelowselfidentificationsurveycompletionoftheformisentirelyvoluntarywhateveryourdecisionitwillnotbeconsideredinthehiringprocessorthereafteranyinformationthatyoudoprovidewillberecordedandmaintainedi'
           OR question_key = 'whatisyourgender'
    """, (gender_options,))

    veteran_options = [
        "I am not a protected veteran",
        "I identify as one or more of the classifications of a protected veteran",
        "I don't wish to answer"
    ]
    cur.execute("""
        UPDATE screening_questions
        SET options = %s,
            answer = 'I am not a protected veteran',
            status = 'ANSWERED',
            updated_at = NOW()
        WHERE question_key = 'veteranstatusvoluntaryselfidentification'
           OR question_key = 'veteranstatus'
    """, (veteran_options,))
    print("✓ Verified Gender and Veteran Status options")

    # 4. Education options
    edu_options = ["High school or equivalent", "Associate", "Bachelor's", "Master's", "Doctorate"]
    cur.execute("""
        UPDATE screening_questions
        SET options = %s,
            answer = 'Bachelor''s',
            status = 'ANSWERED',
            updated_at = NOW()
        WHERE question_key LIKE '%%highestlevelofeducation%%'
    """, (edu_options,))
    print("✓ Verified Education options")

    # 5. Ease of moving to Visakhapatnam options
    cur.execute("""
        UPDATE screening_questions
        SET options = ARRAY['Yes', 'No'],
            answer = 'Yes',
            status = 'ANSWERED',
            updated_at = NOW()
        WHERE question_key = 'easeofmovingtovisakhapatnam'
    """)
    print("✓ Verified Visakhapatnam options")

    # 6. Normalize post rejection reasons for Indeed jobs requiring questionnaire
    post_reasons = {
        "b2c53c1d2d827dd3ead5a07449672a6b": "Questions: Veteran Status (Voluntary Self-Identification); Race/Ethnicity; What is your gender? (Voluntary Self-Identification)",
        "172db56c6f6fd823ca7245b2273dcdb9": "Questions: Have you worked with AWS Services - Lambda, S3, EC2, CloudWatch?; GitHub Profile link:; Portfolio/Projects link(s) (Optional) :",
        "d1b0b8660e8035bc1371eb33b9968bbb": "Questions: What is the highest level of education you have completed?",
        "56aa1595d1a1bb3ae0a3aae96f29d3b4": "Questions: How many years of exp you have with - Dotnet, Angular, LEgacy code (mandate), azure, Ado, Entity framework, SQL",
        "8b7d17f000766c976def11cb86cc1ef0": "Questions: Ease of moving to Visakhapatnam ?; Total Experience in Healthcare in years; Current CTC PA (INR); Expected CTC PA (INR); Earliest date of availability to join; Referred by",
    }
    for pid, r_text in post_reasons.items():
        cur.execute("UPDATE posts SET rejection_reason = %s WHERE id = %s", (r_text, pid))
    print(f"✓ Formatted clean rejection_reason on {len(post_reasons)} posts")

    conn.commit()
    cur.close()
    conn.close()
    print("Enrichment complete.")

if __name__ == "__main__":
    enrich_questions()
