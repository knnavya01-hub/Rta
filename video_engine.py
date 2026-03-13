"""
VIDEO ENGINE — Ṛta
Uses deAPI LTX-Video
Animates 6 scenes + stitches with ffmpeg
"""

import os
import time
import subprocess
import tempfile
import requests
from dotenv import load_dotenv

load_dotenv()

DEAPI_KEY = os.getenv("DEAPI_KEY")
BASE_URL  = "https://api.deapi.ai/api/v1/client"

MOTION_PROMPTS = {
    "gentle":  "gentle subtle movement, soft breathing motion, painterly style preserved, sacred meditative, slow drift, warm golden light",
    "flowing": "soft flowing movement, light shifting gently, watercolor texture preserved, cinematic slow motion, sacred atmosphere",
    "still":   "almost still, barely breathing, subtle light flicker, ink wash painting style, deeply meditative"
}


def animate_scene(image_url: str, scene_text: str, motion: str = "gentle") -> dict:
    motion_prompt = MOTION_PROMPTS.get(motion, MOTION_PROMPTS["gentle"])
    prompt = f"{scene_text}. Watercolor painting style, soft sacred light, painterly not photorealistic. {motion_prompt}."

    headers = {
        "Authorization": f"Bearer {DEAPI_KEY}",
        "Accept": "application/json"
    }

    img_response = requests.get(image_url, timeout=60)
    img_response.raise_for_status()
    img_bytes = img_response.content

    data = {
        "prompt": prompt,
        "model": "Ltx2_19B_Dist_FP8",
        "width": 768,
        "height": 768,
        "frames": 120,
        "fps": 24,
        "seed": 42
    }

    files = {
        "first_frame_image": ("scene.jpg", img_bytes, "image/jpeg")
    }

    try:
        response = requests.post(
            f"{BASE_URL}/img2video",
            headers=headers,
            data=data,
            files=files,
            timeout=60
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        response.raise_for_status()
        result = response.json()

        request_id = result.get("data", {}).get("request_id")
        if not request_id:
            return {"success": False, "error": f"No request_id: {result}", "image_url": image_url}

        video_url = poll_video(request_id)
        if video_url:
            return {"success": True, "video_url": video_url, "scene_text": scene_text}
        else:
            return {"success": False, "error": "Timeout", "image_url": image_url}

    except Exception as e:
        return {"success": False, "error": str(e), "image_url": image_url}


def poll_video(request_id: str, max_wait: int = 300) -> str:
    headers = {"Authorization": f"Bearer {DEAPI_KEY}"}
    start = time.time()
    print(f"Polling: {request_id}")

    while time.time() - start < max_wait:
        try:
            r = requests.get(
                f"{BASE_URL}/request-status/{request_id}",
                headers=headers,
                timeout=15
            )
            d = r.json()
            data = d.get("data", d)
            status = data.get("status", "").lower()
            print(f"Status: {status} | Progress: {data.get('progress', 0)}%")

            if status in ("completed", "done"):
                return data.get("result_url") or data.get("video_url") or data.get("output_url") or data.get("url")
            elif status in ("failed", "error"):
                print(f"Failed: {d}")
                return None

            time.sleep(10)
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(5)

    return None


def download_video(url: str, path: str) -> bool:
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Download error: {e}")
        return False


def stitch_videos(video_paths: list, output_path: str) -> bool:
    try:
        list_path = output_path.replace(".mp4", "_list.txt")
        with open(list_path, "w") as f:
            for p in video_paths:
                f.write(f"file '{p}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(list_path)

        if result.returncode == 0:
            print(f"✅ Stitched video: {output_path}")
            return True
        else:
            print(f"ffmpeg error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Stitch error: {e}")
        return False


def animate_six_scenes(scenes: list) -> dict:
    animated_scenes = []
    clip_paths = []
    tmpdir = tempfile.mkdtemp()

    for i, scene in enumerate(scenes):
        print(f"\nAnimating scene {i+1}/6...")
        result = animate_scene(
            image_url=scene.get("image_url", ""),
            scene_text=scene.get("text_line", scene.get("text", "")),
            motion=scene.get("motion", "gentle")
        )

        scene_out = {**scene, **result}

        if result.get("success") and result.get("video_url"):
            clip_path = os.path.join(tmpdir, f"scene_{i+1}.mp4")
            downloaded = download_video(result["video_url"], clip_path)
            if downloaded:
                clip_paths.append(clip_path)
                scene_out["clip_path"] = clip_path

        animated_scenes.append(scene_out)

        if i < 5:
            time.sleep(2)

    if len(clip_paths) >= 2:
        final_path = os.path.join(tmpdir, "rta_final.mp4")
        stitched = stitch_videos(clip_paths, final_path)
        if stitched:
            return {
                "success": True,
                "final_video_path": final_path,
                "clip_count": len(clip_paths),
                "scenes": animated_scenes
            }

    return {
        "success": len(clip_paths) > 0,
        "final_video_path": clip_paths[0] if clip_paths else None,
        "clip_count": len(clip_paths),
        "scenes": animated_scenes
    }


def animate_three_scenes(scenes: list) -> list:
    animated = []
    for i, scene in enumerate(scenes):
        print(f"Animating scene {i+1}/{len(scenes)}...")
        result = animate_scene(
            image_url=scene.get("image_url", ""),
            scene_text=scene.get("text", scene.get("text_line", "")),
            motion=scene.get("motion", "gentle")
        )
        animated.append({**scene, **result})
        if i < len(scenes) - 1:
            time.sleep(2)
    return animated


def build_painting_prompt(scene_description: str, character: str = None) -> str:
    char = f"{character} depicted as sacred watercolor illustration, painterly not photorealistic, " if character else ""
    return (f"{scene_description}. {char}Indian miniature painting style, soft sacred light, warm gold tones, no text, painterly brushstrokes visible")


if __name__ == "__main__":
    print("\nTesting Ṛta Video Engine (6 scenes + stitch)...\n")
    result = animate_scene(
        image_url="https://image.pollinations.ai/prompt/Arjuna%20drops%20bow%20watercolor%20sacred%20light%20Indian%20painting%20no%20text?width=768&height=768&nologo=true",
        scene_text="Arjuna drops his bow, hands trembling",
        motion="gentle"
    )
    if result["success"]:
        print(f"✅ Video: {result['video_url']}")
    else:
        print(f"❌ Failed: {result['error']}")