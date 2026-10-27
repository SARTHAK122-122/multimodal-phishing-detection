# =====================================================================
# React dashboard - static build served by nginx.
#
# VITE_API_BASE_URL=/api makes the bundle call the same origin, which
# nginx proxies to the backend container (see nginx.conf).
# =====================================================================
FROM node:20-alpine AS build
WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html
EXPOSE 80
