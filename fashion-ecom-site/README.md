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
- Databricks App

## Project Structure

```
fashion-ecom-site/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # API endpoints
│   │   │   ├── products.py      # Product catalog APIs
│   │   │   ├── users.py         # User persona APIs
│   │   │   ├── search.py        # Search & recommendations
│   │   │   └── images.py        # Image serving
│   │   ├── models/              # Pydantic models
│   │   ├── repositories/        # Data access layer
│   │   ├── services/            # Business logic
│   │   ├── core/                # Configuration
│   │   └── main.py              # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── product/         # Product UI components
│   │   │   ├── user/            # User/persona components
│   │   │   ├── layout/          # Layout components
│   │   │   └── ui/              # Base UI components
│   │   ├── pages/               # Page components
│   │   ├── api/                 # API client
│   │   ├── stores/              # Zustand stores
│   │   ├── types/               # TypeScript types
│   │   └── App.tsx
│   └── package.json
├── data/
│   └── personas.json            # User persona seed data
└── databricks.yml               # Databricks App config
```

## Features

### Core Features
- ✅ Product catalog with filtering and pagination
- ✅ Persona-based shopping experience
- ✅ Personalized product recommendations
- ✅ Text-based product search
- ✅ Image-based visual search (CLIP integration ready)
- ✅ Shopping cart (mock)
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
cd backend
pip install -r requirements.txt
```

2. **Configure environment:**
Create a `.env` file in the `backend` directory:
```bash
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your-token
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
CLIP_ENDPOINT=https://your-workspace.cloud.databricks.com/serving-endpoints/your-clip-endpoint/invocations
```

3. **Run the development server:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

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

The Vite proxy will forward `/api/*` requests to the backend.

## API Endpoints

### Products
- `GET /api/products` - List products with filtering and pagination
- `GET /api/products/{id}` - Get product details
- `GET /api/products/filters/options` - Get available filter options

### Users
- `GET /api/users` - List all personas
- `GET /api/users/{id}` - Get persona details
- `GET /api/users/{id}/profile` - Get user profile with purchase history

### Search
- `POST /api/search/text` - Text search
- `POST /api/search/image` - Image upload search
- `GET /api/search/recommendations/{user_id}` - Personalized recommendations

### Images
- `GET /api/images/{path}` - Serve product images

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

## Deployment to Databricks

### Build for Production

1. **Build frontend:**
```bash
cd frontend
npm run build
```

2. **Configure Databricks App:**
Update `databricks.yml` with your workspace details.

3. **Deploy:**
```bash
databricks apps create fashion-ecom-app
```

## Next Steps

### To Complete
- [ ] Full CLIP integration for visual/text search
- [ ] Product detail page with image gallery
- [ ] Search page with image upload UI
- [ ] User profile page
- [ ] Cart page with checkout flow
- [ ] Loading states and error handling
- [ ] Mobile responsiveness refinements
- [ ] Performance optimizations

### Future Enhancements
- [ ] Real-time similarity scoring visualization
- [ ] A/B testing different recommendation algorithms
- [ ] User interaction tracking
- [ ] Advanced filtering (multi-select, ranges)
- [ ] Product comparison
- [ ] Wishlist functionality
- [ ] Review and rating system (mock)

## Development Notes

### Personalization Logic
The recommendation engine considers:
- User price range preferences (25th-75th percentile)
- Color preferences (boost products matching preferred colors)
- Category preferences
- Price deviation from user's average

### Search Implementation
- **Text search**: Currently uses SQL LIKE, ready for CLIP text embeddings
- **Image search**: Ready for CLIP image embeddings with cosine similarity
- **Hybrid search**: Combines both modalities

### Databricks Integration
- Uses Databricks SQL Connector for efficient queries
- Direct access to Unity Catalog tables
- Ready for Model Serving endpoint integration
- Images served from UC Volumes

## Contributing

This is a demo project. Feel free to extend and customize for your needs.

## License

MIT
