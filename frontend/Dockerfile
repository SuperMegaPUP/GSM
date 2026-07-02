FROM node:20-alpine AS builder
ARG API_URL=http://backend:8000
ENV API_URL=http://backend:8000
ENV API_URL=$API_URL
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
ARG API_URL=http://backend:8000
ENV API_URL=$API_URL
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/next.config.mjs ./
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
