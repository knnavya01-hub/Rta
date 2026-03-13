"""
DATABASE ENGINE — Ṛta
Loads translated verses into ChromaDB
Full metadata including Context Layer
"""

import os
import json
import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# ── Setup ChromaDB ────────────────────────────────────────────
chroma_client = chromadb.PersistentClient(path="./rta_db")
collection = chroma_client.get_or_create_collection(
    name="rta_wisdom",
    metadata={"description": "Ṛta Sanskrit wisdom database"}
)

# ── Embedding Model ───────────────────────────────────────────
print("Loading embedding model...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Embedding model ready")


# ── Parse Stage 6 Output ──────────────────────────────────────
def parse_stage6(stage6_text: str) -> dict:
    
    def extract(label, text):
        if label in text:
            line = text.split(label)[1].split("\n")[0].strip()
            return line.strip("*").strip()
        return ""

    def extract_list(label, text):
        raw = extract(label, text)
        items = []
        for item in raw.replace("[", "").replace("]", "").split(","):
            item = item.strip().strip("*").strip()
            if item:
                items.append(item)
        return items

    return {
        "core_wisdom": extract("CORE WISDOM:", stage6_text),
        "story_essence": extract("STORY ESSENCE:", stage6_text),
        "ancient_narrative": extract("ANCIENT NARRATIVE:", stage6_text),
        "modern_parallel": extract("MODERN PARALLEL:", stage6_text),
        "scene_1": extract("SCENE 1:", stage6_text),
        "scene_2": extract("SCENE 2:", stage6_text),
        "scene_3": extract("SCENE 3:", stage6_text),
        "deep_question": extract("DEEP QUESTION:", stage6_text),
        "emotions": extract_list("EMOTIONS:", stage6_text),
        "situations": extract_list("SITUATIONS:", stage6_text),
        "themes": extract_list("THEMES:", stage6_text),
        "archetypes": extract_list("ARCHETYPES:", stage6_text),
        "journey_stages": extract_list("JOURNEY STAGES:", stage6_text),
        "resolution": extract_list("RESOLUTION:", stage6_text),
        "context": extract_list("CONTEXT:", stage6_text),  # ← NEW
    }


# ── Store Verse in ChromaDB ───────────────────────────────────
def store_verse(verse: dict):
    
    parsed = parse_stage6(verse.get("stage6_synthesis", ""))

    search_text = f"""
{parsed.get('core_wisdom', '')}
{parsed.get('story_essence', '')}
{' '.join(parsed.get('emotions', []))}
{' '.join(parsed.get('situations', []))}
{' '.join(parsed.get('themes', []))}
{' '.join(parsed.get('context', []))}
{verse.get('sanskrit_original', '')}
"""

    embedding = embedder.encode(search_text).tolist()

    metadata = {
        "scripture": verse.get("scripture", ""),
        "id": verse.get("id", ""),
        "sanskrit": verse.get("sanskrit_original", "")[:200],
        "transliteration": verse.get("transliteration", "")[:200],
        "core_wisdom": parsed.get("core_wisdom", "")[:500],
        "story_essence": parsed.get("story_essence", "")[:200],
        "ancient_narrative": parsed.get("ancient_narrative", "")[:1000],
        "modern_parallel": parsed.get("modern_parallel", "")[:1000],
        "scene_1": parsed.get("scene_1", "")[:200],
        "scene_2": parsed.get("scene_2", "")[:200],
        "scene_3": parsed.get("scene_3", "")[:200],
        "deep_question": parsed.get("deep_question", "")[:300],
        "emotions": ", ".join(parsed.get("emotions", [])),
        "situations": ", ".join(parsed.get("situations", [])),
        "themes": ", ".join(parsed.get("themes", [])),
        "archetypes": ", ".join(parsed.get("archetypes", [])),
        "journey_stages": ", ".join(parsed.get("journey_stages", [])),
        "resolution": ", ".join(parsed.get("resolution", [])),
        "context": ", ".join(parsed.get("context", [])),  # ← NEW
        "language_status": verse.get("language_status", "Multi-LLM synthesized"),
        "curriculum_context_used": verse.get("curriculum_context_used", "")[:200],
    }

    collection.upsert(
        ids=[verse["id"]],
        embeddings=[embedding],
        documents=[search_text],
        metadatas=[metadata]
    )

    print(f"  ✅ Stored: {verse['id']}")
    return parsed


# ── Load All Verses ───────────────────────────────────────────
def load_all_verses(json_file: str = "translated_verses.json"):
    
    if not os.path.exists(json_file):
        print(f"❌ {json_file} not found!")
        print("Run scripture_pipeline.py first!")
        return False

    with open(json_file, "r", encoding="utf-8") as f:
        all_verses = json.load(f)

    total = 0
    for scripture, verses in all_verses.items():
        print(f"\n📚 Loading {scripture}...")
        for verse in verses:
            store_verse(verse)
            total += 1

    print(f"\n✅ {total} verses loaded into ChromaDB!")
    print(f"✅ Database ready at ./rta_db")
    return True


# ── Search Function ───────────────────────────────────────────
def search_wisdom(
    query: str,
    emotions: list = [],
    situations: list = [],
    journey_stage: str = "",
    archetype: str = "",
    context: str = "",        # ← NEW
    n_results: int = 5,
    exclude_ids: list = []
) -> list:

    search_query = query
    if emotions:
        search_query += " " + " ".join(emotions)
    if situations:
        search_query += " " + " ".join(situations)
    if journey_stage:
        search_query += " " + journey_stage
    if context:
        search_query += " " + context

    query_embedding = embedder.encode(search_query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results + len(exclude_ids), 20),
        include=["metadatas", "distances", "documents"]
    )

    ranked = []
    for i, metadata in enumerate(results["metadatas"][0]):
        verse_id = metadata.get("id", "")

        if verse_id in exclude_ids:
            continue

        distance = results["distances"][0][i]
        semantic_score = max(0, 1 - distance)
        boost = 0

        verse_emotions = metadata.get("emotions", "").split(", ")
        for emotion in emotions:
            if emotion in verse_emotions:
                boost += 0.1

        verse_situations = metadata.get("situations", "").split(", ")
        for situation in situations:
            if situation in verse_situations:
                boost += 0.1

        verse_stages = metadata.get("journey_stages", "").split(", ")
        if journey_stage and journey_stage in verse_stages:
            boost += 0.15

        verse_archetypes = metadata.get("archetypes", "").split(", ")
        if archetype and archetype in verse_archetypes:
            boost += 0.1

        # Context boost ← NEW
        verse_contexts = metadata.get("context", "").split(", ")
        if context and context in verse_contexts:
            boost += 0.1

        final_score = min(1.0, semantic_score + boost)

        ranked.append({
            "id": verse_id,
            "score": final_score,
            "scripture": metadata.get("scripture", ""),
            "core_wisdom": metadata.get("core_wisdom", ""),
            "story_essence": metadata.get("story_essence", ""),
            "ancient_narrative": metadata.get("ancient_narrative", ""),
            "modern_parallel": metadata.get("modern_parallel", ""),
            "scene_1": metadata.get("scene_1", ""),
            "scene_2": metadata.get("scene_2", ""),
            "scene_3": metadata.get("scene_3", ""),
            "deep_question": metadata.get("deep_question", ""),
            "emotions": metadata.get("emotions", ""),
            "situations": metadata.get("situations", ""),
            "journey_stages": metadata.get("journey_stages", ""),
            "context": metadata.get("context", ""),
            "sanskrit": metadata.get("sanskrit", ""),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:n_results]


# ── Stats ─────────────────────────────────────────────────────
def get_stats():
    count = collection.count()
    print(f"\n📊 Database Stats:")
    print(f"  Total verses: {count}")
    print(f"  Location: ./rta_db")
    return count


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🌊 Ṛta Database Engine\n")
    print("Choose:")
    print("1. Load verses into database")
    print("2. Test search")
    print("3. Show stats")

    choice = input("\nEnter 1, 2, or 3: ").strip()

    if choice == "1":
        print("\nLoading verses into ChromaDB...")
        load_all_verses()

    elif choice == "2":
        print("\nTesting search...")
        results = search_wisdom(
            query="I worked hard but got nothing",
            emotions=["Exhaustion"],
            situations=["Career Block"],
            journey_stage="Triggered",
            archetype="Seeker",
            context="Conflict",
            n_results=2
        )
        for r in results:
            print(f"\nMatch: {r['id']} (score: {r['score']:.2f})")
            print(f"Wisdom: {r['core_wisdom']}")
            print(f"Scene 1: {r['scene_1']}")
            print(f"Context: {r['context']}")

    elif choice == "3":
        get_stats()