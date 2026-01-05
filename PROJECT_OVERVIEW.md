# Fashion E-Commerce Visual Search - Project Overview

> **AI-powered visual search and personalized recommendations built on Databricks**

## Architecture

```
User Request → React Frontend → FastAPI Backend → [Lakebase | Model Serving | Vector Search] → Unity Catalog
```

### Tech Stack
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS
- **Backend**: FastAPI + Pydantic + asyncpg/SQLAlchemy
- **Data**: Unity Catalog (Delta Lake) + Lakebase (PostgreSQL sync)
- **ML**: CLIP (multimodal embeddings) + Vector Search + SmolVLM (attribute extraction)
- **Deployment**: Databricks Apps

## Core Features

- ✅ **Text Search**: Semantic product search ("red leather jacket")
- ✅ **Image Search**: Visual similarity search (upload photo → find products)
- ✅ **Personalized Recommendations**: 5 user personas with distinct styles
- ✅ **Cross-Modal Search**: Text query → image results, image query → text matching
- ✅ **Product Catalog**: 44,424 fashion products with filters
- ✅ **Shopping Cart**: Mock checkout flow

## Data Assets

### Unity Catalog: `main.fashion_demo`

**Core Tables:**
- `products` - 44,424 products (master catalog)
- `product_embeddings_multimodal` - CLIP embeddings (image + text + hybrid, 512-dim)
- `user_style_features` - User preference embeddings (10k users)
- `product_extracted_attributes` - Visual attributes from SmolVLM (in progress)

**Images Volume:**
- `/Volumes/main/fashion_demo/raw_data/images/` - 44,424 product JPGs

### Model Serving Endpoints

1. **siglip-multimodal-endpoint** (primary)
   - Text & image → 512-dim embeddings
   - Model: SigLIP multimodal encoder
   - Scale to zero enabled
   - Unified endpoint for both text and image encoding

### Vector Search Indexes

All built on `product_embeddings_multimodal`:
- `vs_image_search` - Visual similarity
- `vs_text_search` - Semantic text search
- `vs_hybrid_search` - Combined (default for recommendations)

## Current Status

### Completed
- ✅ Full-stack app deployed on Databricks Apps
- ✅ Multimodal CLIP embeddings generated for all products
- ✅ Vector Search indexes operational
- ✅ 5 user personas with behavioral data
- ✅ Hybrid recommendation engine (60% vector + 40% rules)
- ✅ Lakebase integration for fast SQL queries

### In Progress
- 🚧 **Visual Attribute Extraction** (SmolVLM-2.2B)
  - Extract material, pattern, style, formality from images
  - Goal: Enrich text descriptions for better search quality
  - Status: Notebook ready, testing on 100 products

### Planned
- Search quality improvements (diversity, re-ranking, query expansion)
- Complete-the-look recommendations
- Learning-to-rank based on user behavior

## Key Milestones

1. **Phase 1**: Basic catalog + search (COMPLETED)
   - Product data ingestion
   - Basic text/image search
   - Simple UI

2. **Phase 2**: Multimodal embeddings (COMPLETED)
   - CLIP model integration
   - Vector Search setup
   - Hybrid embeddings

3. **Phase 3**: Personalization (COMPLETED)
   - User personas
   - Behavioral embeddings
   - Recommendation engine

4. **Phase 4**: Quality improvements (IN PROGRESS)
   - Visual attribute extraction
   - Enhanced text descriptions
   - Improved search relevance

## Performance Metrics

### Search Quality
- **Current Score Ranges**:
  - Text search: 52-55% similarity
  - Image search: 67-70% similarity
  - Recommendations: 64-65% similarity
- **Issue**: Narrow score ranges (2-3% spread) → low differentiation
- **Target**: 10-15% score range for better ranking

### System Performance
- Vector Search latency: 200-500ms
- CLIP text embedding: 50-100ms
- CLIP image embedding: 150-300ms
- Cold start: +5-10 seconds (scale-to-zero)

## Quick Reference

### API Endpoints (all under `/api/v1/`)

**Search:**
- `POST /search/text` - Text search
- `POST /search/image` - Image upload search
- `GET /search/recommendations/{user_id}` - Personalized recs

**Products:**
- `GET /products` - List with filters
- `GET /products/{id}` - Product details

**Users:**
- `GET /users` - List personas
- `GET /users/{id}/profile` - User profile

### Development

```bash
# Backend (FastAPI)
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# Frontend (React)
cd frontend
npm install
npm run dev
```

### Deployment

```bash
# Build frontend
cd frontend && npm run build

# Deploy to Databricks Apps
databricks apps deploy fashion-ecom-app
```

## File Structure

```
fashion-ecom-site/
├── app.py                      # FastAPI entrypoint
├── core/config.py              # Settings & config
├── routes/v1/                  # API routes
│   ├── products.py
│   ├── users.py
│   ├── search.py
│   └── images.py
├── services/                   # Business logic
│   ├── clip_service.py         # CLIP integration
│   └── vector_search_service.py
├── repositories/               # Data access
│   └── lakebase.py
├── models/schemas.py           # Pydantic models
├── frontend/                   # React app
│   └── src/
├── notebooks/                  # Databricks notebooks
│   └── smolvlm_batch_attribute_extraction.py
└── PROJECT_OVERVIEW.md         # This file
```

## Documentation

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - This file
- [LESSONS_LEARNED.md](LESSONS_LEARNED.md) - Key learnings and patterns
- [DATABRICKS_CONTEXT.md](DATABRICKS_CONTEXT.md) - Complete technical reference
- [README.md](README.md) - Original project README

## Authentication

### Databricks Apps (Production)
- OAuth M2M via service principal
- Auto-injected: `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`
- Lakebase uses OAuth token as PostgreSQL password

### Local Development
- `.env` file with personal Databricks token
- Direct connection to workspace

## Support

- **Databricks Docs**: https://docs.databricks.com
- **Vector Search**: https://docs.databricks.com/en/generative-ai/vector-search.html
- **Model Serving**: https://docs.databricks.com/en/machine-learning/model-serving/

---

**Last Updated**: 2025-12-31
**Version**: 2.0
