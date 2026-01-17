# 1. Use an official lightweight Python image
FROM python:3.10-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy requirements first (to cache dependencies and speed up builds)
COPY requirements.txt .

# 4. Install Python dependencies
# --no-cache-dir keeps the image small
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your app code
COPY . .

# 6. Expose the port Railway expects (typically 8080)
EXPOSE 8080

# 7. Run Streamlit
# We explicitly set the port to 8080 and address to 0.0.0.0 so it's accessible externally
CMD streamlit run app.py \
    --server.port=8080 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false