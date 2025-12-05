# Fashion Ecommerce Visual Search Demo

A modern ecommerce storefront experience with AI-powered visual search and personalized recommendations, built on Databricks.

## Architecture

### Tech Stack

**Frontend:**
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- React Router (routing)
- TanStack Query (server state)
- Zustand (client state)
- Axios (HTTP client)

**Backend:**
- FastAPI (Python web framework)
- Databricks SQL Connector (data access via Lakebase)
- Databricks Model Serving (CLIP embeddings)
- Pydantic (data validation)

**Data:**
- Unity Catalog tables (products, users, embeddings, user features)
- UC Volumes (product images)

**Deployment:**
- Databricks Apps

## Project Structure

Following Databricks Apps best practices for FastAPI:

```
fashion-ecom-site/
├── app.py                    # Main FastAPI entrypoint
├── app.yaml                  # Databricks Apps configuration
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
├── routes/                   # API routes (versioned)
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       ├── products.py      # Product catalog APIs
│       ├── users.py         # User persona APIs
│       ├── search.py        # Search & recommendations
│       └── images.py        # Image serving
├── models/                   # Pydantic models
│   ├── __init__.py
│   └── schemas.py
├── repositories/            # Data access layer
│   ├── __init__.py
│   └── lakebase.py
├── core/                    # Configuration
│   ├── __init__.py
│   └── config.py
├── services/                # Business logic (extensible)
│   └── __init__.py
├── data/
│   └── personas.json        # User persona seed data
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── product/     # Product UI components
    │   │   ├── user/        # User/persona components
    │   │   ├── layout/      # Layout components
    │   │   └── ui/          # Base UI components
    │   ├── pages/           # Page components
    │   ├── api/             # API client
    │   ├── stores/          # Zustand stores
    │   ├── types/           # TypeScript types
    │   └── App.tsx
    └── package.json
```

## Features

### Core Features
- ✅ Product catalog with filtering and pagination
- ✅ Persona-based shopping experience (5 distinct profiles)
- ✅ Personalized product recommendations
- ✅ Text-based product search
- ✅ Image-based visual search (CLIP integration ready)
- ✅ Shopping cart with mock checkout
- ✅ Product detail pages
- ✅ User profile pages
- ✅ Responsive design

### User Personas
The demo includes 5 distinct shopping personas:

1. **Budget-Conscious Casual** - Value-focused, everyday wear ($15-$60 range)
2. **Athletic Performance** - Fitness enthusiast, performance gear ($30-$120 range)
3. **Luxury Fashionista** - High-end fashion lover ($100-$500 range)
4. **Workwear Professional** - Career-focused, office attire ($40-$150 range)
5. **Trendy Gen-Z** - Fashion-forward, colorful styles ($20-$80 range)

## Setup & Development

### Prerequisites
- Python 3.9+
- Node.js 18+
- Databricks workspace with:
  - Unity Catalog tables (main.fashion_demo.*)
  - UC Volume with product images
  - SQL warehouse access
  - (Optional) CLIP model serving endpoint

### Backend Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```

Edit `.env` with your Databricks credentials:
```env
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id

# Optional - for CLIP integration
CLIP_ENDPOINT=https://your-workspace.cloud.databricks.com/serving-endpoints/clip/invocations
```

3. **Run the development server:**
```bash
uvicorn app:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

**API Documentation:** http://localhost:8000/docs

### Frontend Setup

1. **Install dependencies:**
```bash
cd frontend
npm install
```

2. **Run the development server:**
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Full Stack Development

Run both servers simultaneously:
- Backend: `http://localhost:8000` (FastAPI)
- Frontend: `http://localhost:3000` (Vite dev server with proxy to backend)

The Vite dev server automatically proxies `/api/*` requests to the backend.

## API Endpoints

All endpoints are versioned under `/api/v1/`:

### Products
- `GET /api/v1/products` - List products with filtering and pagination
- `GET /api/v1/products/{id}` - Get product details
- `GET /api/v1/products/filters/options` - Get available filter options

### Users
- `GET /api/v1/users` - List all personas
- `GET /api/v1/users/{id}` - Get persona details
- `GET /api/v1/users/{id}/profile` - Get user profile with purchase history

### Search
- `POST /api/v1/search/text` - Text search
- `POST /api/v1/search/image` - Image upload search
- `GET /api/v1/search/recommendations/{user_id}` - Personalized recommendations

### Images
- `GET /api/v1/images/{path}` - Serve product images

**Note:** The `/api` prefix is required for Databricks Apps OAuth2 Bearer token authentication.

## Data Schema

### main.fashion_demo.products
- `product_id` - Unique identifier
- `product_display_name` - Display name
- `price` - Price
- `image_path` - Path to image in UC volume
- `gender`, `master_category`, `sub_category`, `article_type` - Product taxonomy
- `base_color`, `season`, `year`, `usage` - Product attributes

### main.fashion_demo.users
- `user_id` - Unique identifier
- `segment` - User segment
- `avg_price_point` - Average price preference
- `preferred_categories` - List of preferred categories

### main.fashion_demo.product_image_embeddings
- `product_id` - Foreign key to products
- `image_embedding` - Vector representation (CLIP)
- `embedding_model` - Model used

### main.fashion_demo.user_style_features
- `user_id` - Foreign key to users
- `user_embedding` - User style vector
- `category_prefs`, `color_prefs`, `brand_prefs` - Preferences
- `min_price`, `max_price`, `avg_price` - Price preferences

## Deployment to Databricks Apps

### Build for Production

1. **Build frontend:**
```bash
cd frontend
npm run build
```

2. **Deploy to Databricks:**
```bash
databricks apps create fashion-ecom-app --source-code-path .
```

The `app.yaml` configuration file specifies:
- Command: `uvicorn app:app`
- Auto-injected Databricks environment variables
- OAuth2-ready with `/api` prefix

### Deployment Configuration

The `app.yaml` follows Databricks Apps best practices:

```yaml
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

env:
  - name: DATABRICKS_HOST
    value: ${workspace.host}
  - name: DATABRICKS_TOKEN
    value: ${workspace.token}
```

## Development Notes

### Personalization Logic
The recommendation engine considers:
- User price range preferences (25th-75th percentile)
- Color preferences (boost products matching preferred colors)
- Category preferences
- Price deviation from user's average
- Personalization explanations ("Why we picked this")

### Search Implementation
- **Text search**: Currently uses SQL LIKE, ready for CLIP text embeddings
- **Image search**: Ready for CLIP image embeddings with cosine similarity
- **Hybrid search**: Combines both modalities

### Databricks Integration
- Uses Databricks SQL Connector for efficient queries
- Direct access to Unity Catalog tables via Lakebase
- Ready for Model Serving endpoint integration
- Images served from UC Volumes
- Parameterized queries for security

## Project Documentation

- **[SETUP_AND_TESTING.md](SETUP_AND_TESTING.md)** - Detailed setup and testing guide
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Complete feature overview
- **[RESTRUCTURING_SUMMARY.md](RESTRUCTURING_SUMMARY.md)** - Databricks Apps best practices migration
- **[FASHION_ECOM-SITE_CONTEXT.md](FASHION_ECOM-SITE_CONTEXT.md)** - Original project context

## Testing

### Test Backend Health
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### Test Products Endpoint
```bash
curl "http://localhost:8000/api/v1/products?page=1&page_size=5"
```

### Test Personas
```bash
curl http://localhost:8000/api/v1/users
```

### Test Recommendations
```bash
curl "http://localhost:8000/api/v1/search/recommendations/user_001?limit=5"
```

## User Flows

1. **Browse Products** - Filter by category, price, color, season
2. **Select Persona** - Choose from 5 distinct shopping profiles
3. **View Recommendations** - Personalized picks based on style
4. **Search Products** - Text or image-based search
5. **Product Details** - View full product information
6. **Add to Cart** - Build shopping cart
7. **Mock Checkout** - Complete demo purchase flow

## Architecture Highlights

### Backend (FastAPI)
- **Flat structure** following Python best practices
- **Versioned APIs** for backwards compatibility
- **Lakebase repository** for Unity Catalog data access
- **Pydantic models** for type safety and validation
- **CORS enabled** for local development

### Frontend (React)
- **Component-based** architecture
- **Type-safe** with TypeScript
- **Server state** managed by TanStack Query
- **Client state** managed by Zustand
- **Responsive** mobile-first design

### Data Flow
1. Frontend → API Client (Axios)
2. FastAPI Routes → Repository Layer
3. Repository → Databricks SQL (Lakebase)
4. Unity Catalog → Delta Tables
5. Response → Pydantic Models → JSON

## Performance Optimizations

- Image lazy loading
- React Query caching (5 min default)
- Code splitting via React Router
- Debounced search input
- Pagination for large datasets
- Optimistic UI updates

## Security

- Parameterized SQL queries (SQL injection prevention)
- Environment-based configuration (no hardcoded credentials)
- CORS configuration
- Unity Catalog access control
- Databricks Apps OAuth2 (when deployed)

## Future Enhancements

- [ ] Full CLIP integration for semantic search
- [ ] Real-time similarity scoring visualization
- [ ] A/B testing different recommendation algorithms
- [ ] User interaction tracking and analytics
- [ ] Advanced filtering (multi-select, ranges)
- [ ] Product comparison feature
- [ ] Wishlist functionality
- [ ] Review and rating system (mock)
- [ ] Mobile app (React Native)

## Contributing

This is a demo project showcasing Databricks + FastAPI + React best practices. Feel free to extend and customize for your needs.

## License

MIT

---

Built with ❤️ using Databricks, FastAPI, and React
