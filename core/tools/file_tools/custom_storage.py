# -*- coding: utf-8 -*-
"""
Custom Storage Tools: Support text + attachment + OCR
"""
import json
from datetime import datetime
from pathlib import Path

def save_custom_data(category: str, content: str, tags: list = None, attachment: str = None, data_dir=None):
    """Save custom data"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    base_dir = data_dir / "custom_storage"
    category_dir = base_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_id = f"{timestamp}_{len(list(category_dir.glob('*')))}"

    record = {
        "id": file_id,
        "category": category,
        "tags": tags or [],
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "attachment": attachment,
        "has_attachment": bool(attachment and Path(attachment).exists()),
        "content_preview": content[:100] + "..." if len(content) > 100 else content,
        "ocr_text": ""
    }

    meta_file = category_dir / f"{file_id}.json"

    final_attachment_path = None
    if attachment and Path(attachment).exists():
        src = Path(attachment)
        dst = category_dir / f"{file_id}{src.suffix}"
        
        is_image = src.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
        
        try:
            src.replace(dst)
            final_attachment_path = str(dst)
            record["attachment"] = final_attachment_path
            
            if is_image:
                print(f"[SmartSave] Image attachment detected, starting OCR engine to extract text...")
                try:
                    import easyocr
                    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False) 
                    results = reader.readtext(final_attachment_path)
                    extracted_text = " ".join([item[1] for item in results])
                    
                    if extracted_text.strip():
                        record["ocr_text"] = extracted_text
                        print(f"[SmartSave] OCR successful! Extracted {len(extracted_text)} characters.")
                        record["content"] = f"{content}\n[Image text content]: {extracted_text}"
                    else:
                        print(f"[SmartSave] No valid text recognized in image.")
                
                except ImportError:
                    print("[SmartSave] easyocr library not installed, skipping OCR. Run: pip install easyocr")
                except Exception as e:
                    print(f"[SmartSave] OCR process error: {e}")
            
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            return {"success": False, "error": f"File move failed: {e}"}
    else:
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

    return {
        "success": True,
        "result": f"Saved to {meta_file}",
        "data": record
    }

def search_custom_storage(category: str = None, query: str = None, limit: int = 5, data_dir=None):
    """Search custom storage"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    base_dir = data_dir / "custom_storage"
    if not base_dir.exists():
        return {
            "success": True,
            "result": [],
            "total_found": 0,
            "error": None
        }

    all_records = []
    search_dirs = []
    
    if category:
        category_dir = base_dir / category
        if category_dir.exists():
            search_dirs.append(category_dir)
    else:
        search_dirs = [d for d in base_dir.iterdir() if d.is_dir()]

    for dir_path in search_dirs:
        for json_file in dir_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                all_records.append(record)
            except Exception as e:
                print(f"[ToolManager] Failed to read record {json_file}: {e}")
                continue

    filtered_records = all_records
    
    if query:
        query_lower = query.lower()
        filtered_records = [
            r for r in filtered_records 
            if (query_lower in r.get("content", "").lower()) or 
               (query_lower in " ".join(r.get("tags", [])).lower()) or
               (query_lower in r.get("category", "").lower()) or
               (query_lower in r.get("ocr_text", "").lower())
        ]
    
    filtered_records.sort(
        key=lambda x: x.get("timestamp", ""), 
        reverse=True
    )
    result_records = filtered_records[:limit]

    return {
        "success": True,
        "result": result_records,
        "total_found": len(filtered_records),
        "error": None
    }
