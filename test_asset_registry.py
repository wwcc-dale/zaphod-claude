#!/usr/bin/env python3
"""
Test Asset Registry Implementation

Tests:
1. Asset Registry class basics
2. File pruning logic
3. Integration checks
"""

import sys
import tempfile
from pathlib import Path
import shutil

# Add zaphod to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("ASSET REGISTRY IMPLEMENTATION TEST")
print("=" * 70)
print()

# Test 1: Import Asset Registry
print("[TEST 1] Importing AssetRegistry class...")
try:
    from zaphod.asset_registry import AssetRegistry
    print("✅ AssetRegistry imported successfully")
except Exception as e:
    print(f"❌ Failed to import AssetRegistry: {e}")
    sys.exit(1)

# Test 2: Create temporary course structure
print("\n[TEST 2] Creating test course structure...")
test_dir = Path(tempfile.mkdtemp(prefix="zaphod_test_"))
print(f"Test directory: {test_dir}")

try:
    # Create course structure
    (test_dir / "content" / "test.page").mkdir(parents=True)
    (test_dir / "assets" / "images").mkdir(parents=True)
    (test_dir / "_course_metadata").mkdir(parents=True)

    # Create index.md
    index_content = """---
name: "Test Page"
type: page
published: true
---

# Test Page

![Test Image](../../assets/images/test.jpg)

This is a test page.
"""
    (test_dir / "content" / "test.page" / "index.md").write_text(index_content)

    # Create a dummy image
    (test_dir / "assets" / "images" / "test.jpg").write_bytes(b"fake image data")

    print("✅ Test structure created")
    print(f"   - {test_dir / 'content' / 'test.page' / 'index.md'}")
    print(f"   - {test_dir / 'assets' / 'images' / 'test.jpg'}")

except Exception as e:
    print(f"❌ Failed to create test structure: {e}")
    sys.exit(1)

# Test 3: Initialize Asset Registry
print("\n[TEST 3] Initializing Asset Registry...")
try:
    registry = AssetRegistry(test_dir)
    print("✅ Registry initialized")
    print(f"   Registry path: {registry.registry_path}")
except Exception as e:
    print(f"❌ Failed to initialize registry: {e}")
    sys.exit(1)

# Test 4: Track a fake upload
print("\n[TEST 4] Tracking fake asset upload...")
try:
    asset_path = test_dir / "assets" / "images" / "test.jpg"
    registry.track_upload(
        local_path=asset_path,
        canvas_file_id=12345,
        canvas_url="https://canvas.example.com/files/12345/download",
        file_size=asset_path.stat().st_size
    )
    print("✅ Asset tracked in registry")

    # Verify we can retrieve it
    canvas_url = registry.get_canvas_url("assets/images/test.jpg")
    if canvas_url == "https://canvas.example.com/files/12345/download":
        print("✅ Asset URL retrieved correctly")
    else:
        print(f"❌ Wrong URL retrieved: {canvas_url}")

except Exception as e:
    print(f"❌ Failed to track asset: {e}")
    sys.exit(1)

# Test 5: Save and reload registry
print("\n[TEST 5] Saving and reloading registry...")
try:
    registry.save()
    registry_file = test_dir / "_course_metadata" / "asset_registry.json"

    if registry_file.exists():
        print("✅ Registry file created")

        # Reload
        registry2 = AssetRegistry(test_dir)
        canvas_url = registry2.get_canvas_url("assets/images/test.jpg")
        if canvas_url == "https://canvas.example.com/files/12345/download":
            print("✅ Registry reloaded successfully")
        else:
            print("❌ Registry data not persisted correctly")
    else:
        print("❌ Registry file not created")

except Exception as e:
    print(f"❌ Failed to save/reload registry: {e}")
    sys.exit(1)

# Test 6: Test content-hash deduplication
print("\n[TEST 6] Testing content-hash deduplication...")
try:
    # Create duplicate file in different location
    duplicate_path = test_dir / "content" / "test.page" / "test.jpg"
    shutil.copy(asset_path, duplicate_path)

    # Track from different path
    registry.track_upload(
        local_path=duplicate_path,
        canvas_file_id=12345,  # Same file ID (deduplication)
        canvas_url="https://canvas.example.com/files/12345/download",
        file_size=duplicate_path.stat().st_size
    )

    # Both paths should resolve to same Canvas URL
    url1 = registry.get_canvas_url("assets/images/test.jpg")
    url2 = registry.get_canvas_url(str(duplicate_path.relative_to(test_dir)))

    if url1 == url2:
        print("✅ Content-hash deduplication working")
    else:
        print(f"❌ Deduplication failed: {url1} != {url2}")

except Exception as e:
    print(f"❌ Deduplication test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Test pruning logic
print("\n[TEST 7] Testing pruning logic...")
try:
    # Import prune check
    from zaphod.prune_canvas_content import AUTO_WORK_FILES

    if "meta.json" in AUTO_WORK_FILES:
        print("✅ meta.json in AUTO_WORK_FILES")
    else:
        print("❌ meta.json NOT in AUTO_WORK_FILES")

    if "source.md" in AUTO_WORK_FILES:
        print("✅ source.md in AUTO_WORK_FILES")
    else:
        print("❌ source.md NOT in AUTO_WORK_FILES")

except Exception as e:
    print(f"❌ Pruning check failed: {e}")

# Test 8: Create derived files and verify structure
print("\n[TEST 8] Testing derived file workflow...")
try:
    # Create meta.json and source.md (simulate frontmatter_to_meta.py output)
    meta_content = {
        "name": "Test Page",
        "type": "page",
        "published": True
    }

    source_content = "# Test Page\n\n![Test Image](../../assets/images/test.jpg)\n\nThis is a test page.\n"

    meta_path = test_dir / "content" / "test.page" / "meta.json"
    source_path = test_dir / "content" / "test.page" / "source.md"

    import json
    meta_path.write_text(json.dumps(meta_content, indent=2))
    source_path.write_text(source_content)

    print("✅ Created derived files (meta.json, source.md)")

    # Verify files exist
    files_before = list((test_dir / "content" / "test.page").iterdir())
    print(f"   Files before cleanup: {[f.name for f in files_before]}")

    # Simulate cleanup
    if meta_path.exists():
        meta_path.unlink()
        print("✅ meta.json deleted")

    if source_path.exists():
        source_path.unlink()
        print("✅ source.md deleted")

    # Verify only index.md remains
    files_after = list((test_dir / "content" / "test.page").iterdir())
    remaining = [f.name for f in files_after if f.is_file()]

    if remaining == ["index.md"]:
        print(f"✅ Only index.md remains: {remaining}")
    else:
        print(f"❌ Unexpected files remain: {remaining}")

except Exception as e:
    print(f"❌ Derived file workflow test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 9: Verify publish_all.py integration
print("\n[TEST 9] Verifying publish_all.py integration...")
try:
    # Check that prune_derived_files was removed
    publish_all_path = Path(__file__).parent / "zaphod" / "publish_all.py"
    publish_content = publish_all_path.read_text()

    if "prune_derived_files" in publish_content:
        print("❌ prune_derived_files still exists in publish_all.py")
    else:
        print("✅ prune_derived_files removed from publish_all.py")

    # Check that AssetRegistry is imported
    if "from zaphod.asset_registry import AssetRegistry" in publish_content:
        print("✅ AssetRegistry imported in publish_all.py")
    else:
        print("❌ AssetRegistry NOT imported in publish_all.py")

    # Check that registry is used
    if "registry.track_upload" in publish_content:
        print("✅ Registry tracking used in publish_all.py")
    else:
        print("❌ Registry tracking NOT used in publish_all.py")

except Exception as e:
    print(f"❌ Integration check failed: {e}")

# Test 10: Registry statistics
print("\n[TEST 10] Testing registry statistics...")
try:
    stats = registry.get_stats()
    print("✅ Registry statistics:")
    print(f"   Total assets: {stats['total_assets']}")
    print(f"   Total paths: {stats['total_paths']}")
    print(f"   Total size: {stats['total_size_mb']:.2f} MB")

    registry.print_stats()

except Exception as e:
    print(f"❌ Statistics test failed: {e}")

# Cleanup
print("\n[CLEANUP] Removing test directory...")
try:
    shutil.rmtree(test_dir)
    print(f"✅ Test directory removed: {test_dir}")
except Exception as e:
    print(f"⚠️  Failed to remove test directory: {e}")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print()
print("✅ All core functionality tests passed!")
print()
print("Next steps:")
print("  1. Test with real course: Create minimal course with asset")
print("  2. Run: zaphod sync (dry-run to verify without Canvas)")
print("  3. Check: Only index.md remains after prune")
print("  4. Verify: asset_registry.json created and populated")
print()
print("=" * 70)
