# Data Mismatch Fixes - December 8, 2025

## Issues Fixed

### 1. ✅ Product ID Type Mismatch

**Problem**: Database returns `product_id` as `int`, but Pydantic models expect `str`

**Error**:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ProductDetail
product_id
  Input should be a valid string [type=string_type, input_value=18412, input_type=int]
```

**Solution**: Added Pydantic field validators to coerce `int` to `str` for all ID fields

**Files Modified**: [models/schemas.py](models/schemas.py)

**Changes**:
```python
# Added to Product, User, UserStyleFeatures, and ProductImageEmbedding models

@field_validator('product_id', mode='before')  # or 'user_id'
@classmethod
def coerce_product_id_to_str(cls, v: Union[str, int]) -> str:
    """Convert product_id to string if it's an int (handles DB type mismatch)"""
    return str(v) if v is not None else None
```

**Impact**: All models now accept both `int` and `str` for ID fields and automatically convert to `str`

---

### 2. ✅ Image URL Conversion (Volume Paths → Accessible URLs)

**Problem**: Image paths stored in database point to Unity Catalog Volumes (e.g., `/Volumes/main/fashion_demo/raw_data/images/12345.jpg`), which are not directly accessible from Databricks Apps or browsers.

**Solution**: Implemented app backend proxy using Databricks Files REST API

**Files Modified**:
- [routes/v1/images.py](routes/v1/images.py) - Image proxy endpoint
- [app.yaml](app.yaml) - UC Volume permissions

**Implementation Pattern** (Recommended by Databricks):

Uses the **Databricks Files REST API** from app backend to read bytes from volume paths:
```
GET /api/2.0/fs/files/Volumes/<catalog>/<schema>/<volume>/<path>
```

**Code**:
```python
from databricks.sdk import WorkspaceClient
import mimetypes

w = WorkspaceClient()  # Uses app's built-in service principal auth

@app.get("/image")
async def get_image(image_path: str):
    volume_path = f"/Volumes/main/fashion_demo/raw_data/images/{image_path}"

    download = w.files.download(volume_path)
    content = download.contents.read()

    mime_type, _ = mimetypes.guess_type(volume_path)

    return Response(
        content=content,
        media_type=mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300"}
    )
```

**UC Permissions** ([app.yaml](app.yaml)):
```yaml
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_demo.raw_data
      privilege: READ_VOLUME
```

This grants the app's service principal READ access to the UC Volume.

**Supported Formats**:
- All formats auto-detected via `mimetypes.guess_type()`
- Common: JPEG, PNG, GIF, WebP, SVG, etc.

**Example Usage**:
```bash
# Just filename
GET /api/v1/images/12345.jpg

# Relative path
GET /api/v1/images/images/12345.jpg

# Full volume path
GET /api/v1/images/Volumes/main/fashion_demo/raw_data/images/12345.jpg
```

**Benefits**:
- ✅ Images accessible from Databricks Apps and browsers
- ✅ Uses app's built-in service principal auth
- ✅ No CORS/cookie issues
- ✅ Automatic MIME type detection
- ✅ Private caching (5 minutes)
- ✅ UC access control maintained

---

## Testing

### Test Product List Endpoint
```bash
curl https://your-app-url/api/v1/products?page=1&page_size=5
```

**Expected Response**:
```json
{
  "products": [
    {
      "product_id": "18412",  // ✅ Now a string
      "product_display_name": "...",
      "price": 99.99,
      "image_path": "/Volumes/main/fashion_demo/raw_data/images/18412.jpg",
      "image_url": "/api/v1/images//Volumes/main/fashion_demo/raw_data/images/18412.jpg",  // ✅ Works!
      ...
    }
  ],
  "total": 1000,
  "page": 1,
  "page_size": 5,
  "has_more": true
}
```

### Test Image Endpoint
```bash
# Direct image access
curl https://your-app-url/api/v1/images/18412.jpg -o test_image.jpg

# Or open in browser
open https://your-app-url/api/v1/images/18412.jpg
```

---

## Files Modified Summary

| File | Changes | Purpose |
|------|---------|---------|
| [models/schemas.py](models/schemas.py) | Added `field_validator` to 4 models | Fix int→str coercion for IDs |
| [routes/v1/images.py](routes/v1/images.py) | Implemented Files API proxy | Serve images from UC Volumes via Files API |
| [app.yaml](app.yaml) | Added `resources.uc_securable` | Grant app READ_VOLUME permission |
| [routes/v1/products.py](routes/v1/products.py) | No changes needed | Already sets `image_url` correctly |

---

## Technical Details

### Pydantic V2 Field Validators

Used `mode='before'` to intercept values before Pydantic validation:

```python
from pydantic import field_validator
from typing import Union

@field_validator('product_id', mode='before')
@classmethod
def coerce_product_id_to_str(cls, v: Union[str, int]) -> str:
    return str(v) if v is not None else None
```

This handles data type mismatches between database schema (int) and API schema (string).

### Databricks Files API

Uses the SDK's Files API to download volume files:

```python
from databricks.sdk import WorkspaceClient
import mimetypes

w = WorkspaceClient()  # Uses app's built-in service principal auth

# Download file from volume
# Calls: GET /api/2.0/fs/files/Volumes/<catalog>/<schema>/<volume>/<path>
download = w.files.download("/Volumes/catalog/schema/volume/path")
content = download.contents.read()

# Auto-detect MIME type
mime_type, _ = mimetypes.guess_type(volume_path)

# Return as HTTP response
return Response(
    content=content,
    media_type=mime_type or "application/octet-stream",
    headers={"Cache-Control": "private, max-age=300"}
)
```

**Authentication**: Automatically handled by `WorkspaceClient()` using the app's built-in service principal (OAuth M2M)

**Permissions**: App must have `READ_VOLUME` privilege on the UC Volume (configured in `app.yaml`)

---

## Deployment

### 1. Commit Changes
```bash
git add models/schemas.py routes/v1/images.py app.yaml DATA_MISMATCH_FIXES.md
git commit -m "fix: Handle int product_ids and serve images from UC Volumes via Files API"
git push
```

### 2. Deploy to Databricks Apps
```bash
databricks apps deploy fashion-ecom-site
```

**Note**: The `app.yaml` changes grant your app's service principal `READ_VOLUME` permission on `main.fashion_demo.raw_data`. This is applied automatically during deployment.

### 3. Verify
1. Check logs for startup (should show no more validation errors)
2. Test products API: `GET /api/v1/products?page=1&page_size=5`
3. Test image serving: Open `{app_url}/api/v1/images/18412.jpg` in browser
4. Verify images display in frontend

---

## Rollback Plan

If issues occur:

### Revert Changes
```bash
git revert HEAD
git push
databricks apps deploy fashion-ecom-site
```

### Alternative: Convert IDs in Repository Layer
If field validators cause issues, you can convert IDs in the repository instead:

```python
# In repositories/lakebase.py, modify _execute_query:

async def _execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    result = await self.session.execute(text(query), params or {})
    columns = result.keys()
    rows = result.fetchall()

    results = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        # Convert ID fields to strings
        if 'product_id' in row_dict:
            row_dict['product_id'] = str(row_dict['product_id'])
        if 'user_id' in row_dict:
            row_dict['user_id'] = str(row_dict['user_id'])
        results.append(row_dict)

    return results
```

---

## Future Improvements

### 1. Image Optimization
- Add image resizing/thumbnails (use Pillow)
- Generate multiple sizes (small, medium, large)
- Compress images before serving

### 2. CDN Integration
- Upload images to Azure Blob/S3
- Serve via CDN for better performance
- Use presigned URLs with expiration

### 3. Caching
- Implement Redis cache for frequently accessed images
- Cache image bytes to avoid repeated Files API calls
- Use ETags for conditional requests

### 4. Lazy Loading
- Implement pagination for images
- Only load images in viewport
- Use placeholder images during loading

---

## Reference

- **Databricks SDK Files API**: https://databricks-sdk-py.readthedocs.io/en/latest/workspace/files.html
- **Pydantic V2 Validators**: https://docs.pydantic.dev/latest/concepts/validators/
- **FastAPI Response Classes**: https://fastapi.tiangolo.com/advanced/custom-response/
