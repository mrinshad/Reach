#!/usr/bin/env python3
"""
Clean up bogus option-questions and populate missing options for screening questions.
(scripts/cleanup_screening_questions.py)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.connection import get_connection

def main():
    conn = get_connection()
    cur = conn.cursor()

    print("--- 1. Removing bogus option-questions ---")
    bogus_keys = [
        'male',
        'female',
        'yes',
        'no',
        'declinetoselfidentify',
        'idontwishtoanswer',
        'iamnotaprotectedveteran',
        'iidentifyasoneormoreoftheclassificationsofaprotectedveteran',
    ]

    for bk in bogus_keys:
        cur.execute("DELETE FROM screening_questions WHERE question_key = %s RETURNING question_text;", (bk,))
        deleted = cur.fetchall()
        if deleted:
            print(f"  ✓ Deleted bogus question: {deleted[0][0]}")

    print("\n--- 2. Updating / inserting clean questions with proper options ---")

    # 1. Gender question
    cur.execute("""
        UPDATE screening_questions
        SET question_text = 'What is your gender? (Voluntary Self-Identification)',
            options = ARRAY['Male', 'Female', 'Decline To Self Identify', 'I don''t wish to answer'],
            answer = 'Male',
            status = 'ANSWERED',
            category = 'demographic'
        WHERE question_key LIKE '%forgovernmentreportingpurposesweaskcandidatestorespondtothebelowselfidentificationsurvey%';
    """)
    print("  ✓ Updated Gender question with options: ['Male', 'Female', 'Decline To Self Identify', \"I don't wish to answer\"]")

    # 2. Veteran Status question
    cur.execute("""
        INSERT INTO screening_questions (id, question_key, question_text, category, answer, is_standard, options, status, occurrences, sample_jobs)
        VALUES (
            'q_veteran_status_xo',
            'veteranstatusvoluntaryselfidentification',
            'Veteran Status (Voluntary Self-Identification)',
            'demographic',
            'I am not a protected veteran',
            TRUE,
            ARRAY['I am not a protected veteran', 'I identify as one or more of the classifications of a protected veteran', 'I don''t wish to answer'],
            'ANSWERED',
            2,
            ARRAY['Full Stack Engineer (Front-End) @ XO Health Inc.']
        )
        ON CONFLICT (question_key) DO UPDATE
        SET options = EXCLUDED.options,
            answer = EXCLUDED.answer,
            status = 'ANSWERED',
            question_text = EXCLUDED.question_text;
    """)
    print("  ✓ Added / Updated Veteran Status with options")

    # 3. Ease of moving to Visakhapatnam
    cur.execute("""
        UPDATE screening_questions
        SET options = ARRAY['Yes', 'No'],
            answer = 'Yes',
            status = 'ANSWERED'
        WHERE question_key = 'easeofmovingtovisakhapatnam';
    """)
    print("  ✓ Updated 'Ease of moving to Visakhapatnam ?' with options: ['Yes', 'No'] and answer: 'Yes'")

    # 4. AWS Services question
    cur.execute("""
        UPDATE screening_questions
        SET options = ARRAY['Yes', 'No']
        WHERE question_key = 'haveyouworkedwithawsserviceslambdas3ec2cloudwatch';
    """)
    print("  ✓ Updated 'Have you worked with AWS Services...' with options: ['Yes', 'No']")

    # 5. Education Level question
    cur.execute("""
        UPDATE screening_questions
        SET question_text = 'What is the highest level of education you have completed?',
            options = ARRAY['High school or equivalent', 'Associate', 'Bachelor''s', 'Master''s', 'Doctorate'],
            answer = 'Bachelor''s',
            status = 'ANSWERED'
        WHERE question_key LIKE '%whatisthehighestlevelofeducationyouhavecompleted%';
    """)
    print("  ✓ Cleaned up education level prompt and added options: ['High school or equivalent', 'Associate', \"Bachelor's\", \"Master's\", 'Doctorate']")

    # 6. Total Experience in Years
    cur.execute("""
        UPDATE screening_questions
        SET answer = '3',
            status = 'ANSWERED'
        WHERE question_key = 'totalexperienceinyears' AND (answer IS NULL OR answer = '');
    """)
    print("  ✓ Updated 'Total Experience in Years' with answer: '3'")

    # 7. Earliest date of availability
    cur.execute("""
        UPDATE screening_questions
        SET answer = 'Immediate',
            status = 'ANSWERED'
        WHERE question_key = 'earliestdateofavailabilitytojoin' AND (answer IS NULL OR answer = '');
    """)
    print("  ✓ Updated 'Earliest date of availability to join' with answer: 'Immediate'")

    print("\n--- 3. Cleaning up rejection reasons on posts ---")
    cur.execute("""
        UPDATE posts
        SET rejection_reason = 'Requires answers for: What is your gender?, Veteran Status'
        WHERE id = 'b2c53c1d2d827dd3ead5a07449672a6b';
    """)
    cur.execute("""
        UPDATE posts
        SET rejection_reason = 'Requires answers for: Total Experience in Years, Ease of moving to Visakhapatnam ?'
        WHERE id = '8b7d17f000766c976def11cb86cc1ef0';
    """)
    cur.execute("""
        UPDATE posts
        SET rejection_reason = 'Requires answers for: What is the highest level of education you have completed?'
        WHERE id = 'd1b0b8660e8035bc1371eb33b9968bbb';
    """)
    print("  ✓ Cleaned up rejection reasons in posts table.")

    conn.commit()
    conn.close()
    print("\n✅ Database cleanup and options update successfully completed!")

if __name__ == "__main__":
    main()
