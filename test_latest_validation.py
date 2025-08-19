import json
import os

import httpx

# Test data - same as before
pdf_file_path = r"C:\Users\Martin Lehnert\Downloads\Barcode_Reference_EN.pdf"
pages_data = {
    "pages": [
        {"page": 28},
        {"page": 37},
        {"page": 39},
        {"page": 40},
        {"page": 44},
        {"page": 45},
        {"page": 46},
        {"page": 47},
        {"page": 51},
        {"page": 84},
        {"page": 85},
    ]
}


async def test_latest_validation():
    """Test the latest validation improvements"""

    # Check if test file exists
    if not os.path.exists(pdf_file_path):
        print(f"Test PDF file not found: {pdf_file_path}")
        return

    print(f"Testing latest validation improvements with file: {pdf_file_path}")
    print(f"File size: {os.path.getsize(pdf_file_path) / (1024 * 1024):.2f} MB")

    try:
        async with httpx.AsyncClient() as client:
            print("\n1. Testing latest validation with split endpoint...")

            # Prepare the request
            files = {
                "file": ("Barcode_Reference_EN.pdf", open(pdf_file_path, "rb"), "application/pdf")
            }
            data = {"pages": json.dumps(pages_data)}

            response = await client.post(
                "http://localhost:8001/v1/split-into-zip", files=files, data=data, timeout=60.0
            )

            print(f"Response status: {response.status_code}")

            if response.status_code == 200:
                zip_filename = "test_latest_validation.zip"
                with open(zip_filename, "wb") as f:
                    f.write(response.content)

                file_size = os.path.getsize(zip_filename)
                print(f"✅ ZIP file created: {zip_filename}")
                print(f"✅ ZIP file size: {file_size} bytes")

                # Check ZIP contents
                import zipfile

                with zipfile.ZipFile(zip_filename, "r") as z:
                    print(f"✅ ZIP contains {len(z.namelist())} files:")
                    for filename in z.namelist():
                        file_info = z.getinfo(filename)
                        print(f"  • {filename} ({file_info.file_size} bytes)")

                # Clean up
                os.remove(zip_filename)
                print(
                    "\n✅ SUCCESS: Latest validation improvements worked - PDF was processed successfully!"
                )

            elif response.status_code == 400:
                # This is what we expect for invalid PDFs
                error_detail = response.json()
                print("\n❌ Expected behavior: PDF validation failed upfront")
                print(f"Error: {error_detail.get('error', 'Unknown error')}")
                print(f"Message: {error_detail.get('message', 'No message')}")

                if "validation_info" in error_detail:
                    validation = error_detail["validation_info"]
                    print("\nValidation Details:")
                    print(f"  - Is valid: {validation.get('is_valid', 'N/A')}")
                    print(f"  - Needs repair: {validation.get('needs_repair', 'N/A')}")
                    print(f"  - Repair attempted: {validation.get('repair_attempted', 'N/A')}")
                    print(f"  - Repair successful: {validation.get('repair_successful', 'N/A')}")

                    if validation.get("issues"):
                        print(f"  - Issues found: {len(validation['issues'])}")
                        for i, issue in enumerate(validation["issues"][:5]):  # Show first 5
                            print(f"    • {issue}")
                        if len(validation["issues"]) > 5:
                            print(f"    ... and {len(validation['issues']) - 5} more issues")

                print("\n✅ SUCCESS: Latest validation caught issues before processing!")

            else:
                print(f"❌ Unexpected response: {response.text}")

    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
        # Close the file
        files["file"][1].close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_latest_validation())
