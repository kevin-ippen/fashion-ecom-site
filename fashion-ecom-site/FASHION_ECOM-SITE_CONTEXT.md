## **Project Context: Fashion Visual Search Ecommerce Rebuild**

### **Objective**

Re-architect the current fashion visual search demo to deliver a realistic ecommerce storefront experience, moving beyond Streamlit to a modern web stack (e.g., React frontend, FastAPI backend), while leveraging Databricks-native capabilities for data management, model serving, and integration.

### **Core Requirements & Considerations**

1. **Data Access & Management**  
   * Use Databricks Lakehouse (Lakebase) for unified, scalable, and secure data storage and access.  
   * Ensure all catalog queries (product search, filtering, recommendations) are powered by this table.  
   * Maintain compatibility with Unity Catalog for governance, permissions, and lineage tracking  
   * 1  
   * .  
2. **Model Serving**  
   * Serve ML models (e.g., visual search, recommendations) using Databricks Model Serving or MLflow, ensuring endpoints are accessible to the new backend  
   * 2  
   * .  
   * Plan for real-world integration: endpoints should be RESTful and easily consumed by FastAPI.  
3. **Backend API**  
   * Implement a FastAPI backend to:  
     * Expose product catalog endpoints (search, filter, detail lookup).  
     * Proxy requests to Databricks model serving endpoints.  
     * Handle user session, cart, and checkout logic (mock or real).  
   * Ensure backend can efficiently query Databricks tables (via Databricks SQL, JDBC, or REST API).  
4. **Frontend**  
   * Build a React-based storefront for a modern ecommerce UI/UX.  
   * Integrate with FastAPI for all data and model interactions.  
   * Support features like product search, filtering, recommendations, and visual search.  
5. **Reintegration & Modularity**  
   * Design components (data access, model serving, API, frontend) to be loosely coupled for easy reintegration.  
   * Document API contracts and data schemas to minimize friction when reconnecting to Databricks-native services.  
6. **Databricks-Native Functionality**  
   * Leverage Databricks for:  
     * Data storage and querying (Lakebase, Unity Catalog).  
     * Model training, tracking, and serving (MLflow, Model Serving).  
     * Feature management for ML (if applicable)  
     * 1  
     * .  
   * Avoid vendor lock-in on the frontend/backend, but maximize Databricks for data and ML.  
7. **Security & Governance**  
   * Use Unity Catalog for data access control and auditability  
   * 1  
   * .  
   * Secure API endpoints and model serving with appropriate authentication (e.g., OAuth, Databricks secrets)  
   * 3  
   * .

### **Future-Proofing**

* Ensure all new components are well-documented and tested.  
* Plan for scalability (data volume, user load).  
* Keep the option open for further enhancements (e.g., real payment integration, user accounts).

**Data Overview**

### **1\.** main.fashion\_demo.products

**Columns and Types:**

* product\_id (string/integer): Unique identifier for each product.  
* gender (string): Target gender (e.g., "Men", "Women", "Unisex").  
* master\_category (string): High-level category (e.g., "Apparel", "Footwear").  
* sub\_category (string): Subdivision of master category (e.g., "Tops", "Shoes").  
* article\_type (string): Specific product type (e.g., "T-shirt", "Sneakers").  
* base\_color (string): Main color (e.g., "Red", "Blue").  
* season (string): Seasonality (e.g., "Summer", "Winter").  
* year (integer): Year of release or addition.  
* usage (string): Intended use (e.g., "Casual", "Sports").  
* product\_display\_name (string): Human-readable product name.  
* price (float/integer): Product price.  
* image\_path (string): Path or URL to product image.  
* ingested\_at (timestamp): When the product was added to the catalog.

**Row Count:**  
Typically, a demo fashion catalog might have 10,000–50,000 rows, but this can vary.

---

### **2\.** main.fashion\_demo.users

**Columns and Types:**

* user\_id (string/integer): Unique identifier for each user.  
* avg\_price\_point (float): Average price of products the user interacts with.  
* created\_date (timestamp): When the user account was created.  
* preferred\_categories (array/string): List of preferred categories (e.g., \["Tops", "Shoes"\]).  
* segment (string): User segment (e.g., "Bargain Hunter", "Luxury Shopper").

**Row Count:**  
Demo datasets often have 1,000–10,000 users.

---

### **3\.** main.fashion\_demo.product\_image\_embeddings

**Columns and Types:**

* product\_id (string/integer): Foreign key to products table.  
* image\_embedding (array\[float\]): Vector representation of product image (e.g., 512 or 768 floats).  
* embedding\_model (string): Model used to generate embedding (e.g., "clip-ViT-B/32").  
* embedding\_dimension (integer): Length of the embedding vector.  
* created\_at (timestamp): When the embedding was generated.

**Row Count:**  
Should match the number of products (1:1 mapping), so expect 10,000–50,000 rows.

---

### **4\.** main.fashion\_demo.user\_style\_features

**Columns and Types:**

* user\_id (string/integer): Foreign key to users table.  
* segment (string): User segment (as above).  
* category\_prefs (array/string): Preferred categories.  
* brand\_prefs (array/string): Preferred brands.  
* color\_prefs (array/string): Preferred colors.  
* min\_price (float): Minimum price user typically shops for.  
* max\_price (float): Maximum price user typically shops for.  
* avg\_price (float): Average price user shops for.  
* p25\_price (float): 25th percentile price.  
* p75\_price (float): 75th percentile price.  
* user\_embedding (array\[float\]): Vector representation of user style (e.g., 128 or 256 floats).  
* num\_interactions (integer): Number of catalog interactions.  
* created\_at (timestamp): When the features were generated.

**Row Count:**  
Should match the number of users (1:1 mapping), so expect 1,000–10,000 rows.

---

### **Data Profiling Tips**

* Use df.dtypes to confirm column types in Databricks notebooks.  
* Use df.describe() for numeric columns to get min, max, mean, percentiles.  
* Use df.count() for row counts.  
* For arrays or embeddings, check len() of a sample entry to confirm dimensions.  
* For string columns, use df.select("column").distinct().show() to see unique values.  
* 

