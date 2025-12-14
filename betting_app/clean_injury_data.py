"""
Clean existing predictions to remove QUESTIONABLE and INJURED RESERVE players
Only keep OUT players in injury reports
"""
import re
from database.db import SessionLocal
from database.models import Prediction

def clean_injury_report(reasoning_text):
    """Remove QUESTIONABLE and INJURED RESERVE players from reasoning text"""
    if not reasoning_text or "**Injury Report:**" not in reasoning_text:
        return reasoning_text

    lines = reasoning_text.split('\n')
    cleaned_lines = []
    in_injury_section = False
    out_players = []

    for line in lines:
        # Check if we're entering injury section
        if "**Injury Report:**" in line:
            in_injury_section = True
            continue  # Skip the header line, we'll add it back if needed

        # Check if we're leaving injury section (next section starts with **)
        if in_injury_section and line.strip().startswith("**") and "Injury Report" not in line:
            in_injury_section = False

            # Add injury section back if we have OUT players
            if out_players:
                cleaned_lines.append(f"\n**Injury Report:** {len(out_players)} player{'s' if len(out_players) != 1 else ''} ruled OUT")
                cleaned_lines.extend(out_players)

            # Add the new section
            cleaned_lines.append(line)
            continue

        # If in injury section, only keep OUT players
        if in_injury_section:
            if ": OUT -" in line:
                # This is an OUT player, keep it
                out_players.append(line)
            # Skip all other lines in injury section (QUESTIONABLE, INJURED RESERVE, descriptions, etc.)
            continue

        # Not in injury section, keep the line
        cleaned_lines.append(line)

    # Handle case where injury section is at the end
    if in_injury_section and out_players:
        cleaned_lines.append(f"\n**Injury Report:** {len(out_players)} player{'s' if len(out_players) != 1 else ''} ruled OUT")
        cleaned_lines.extend(out_players)

    return '\n'.join(cleaned_lines)

def main():
    db = SessionLocal()
    try:
        # Get all predictions
        predictions = db.query(Prediction).all()

        print(f"Found {len(predictions)} predictions to clean")

        updated_count = 0
        for pred in predictions:
            if pred.reasoning and "**Injury Report:**" in pred.reasoning:
                cleaned_reasoning = clean_injury_report(pred.reasoning)

                if cleaned_reasoning != pred.reasoning:
                    pred.reasoning = cleaned_reasoning
                    updated_count += 1
                    print(f"✓ Cleaned prediction {pred.id} for {pred.selection}")

        db.commit()
        print(f"\n✅ Updated {updated_count} predictions")
        print(f"📊 {len(predictions) - updated_count} predictions had no injury data to clean")

    finally:
        db.close()

if __name__ == "__main__":
    main()
