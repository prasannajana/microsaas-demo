# Security headers shared by every location (envsubst template, see nginx.conf).
# API_ORIGIN is the backend origin the SPA calls (VITE_API_URL), e.g. https://api.example.com.
# style-src needs 'unsafe-inline' for Chakra UI / Emotion runtime <style> tags.
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.googleusercontent.com https://avatars.githubusercontent.com; font-src 'self' data:; connect-src 'self' ${API_ORIGIN}; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" always;
add_header Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=(), browsing-topics=()" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
