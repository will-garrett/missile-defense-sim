# Dockerfile for Next.js Frontend

# 1. Builder Stage: Install dependencies and build the application
FROM node:18-alpine AS builder
WORKDIR /app

# Copy package.json and lock file
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build the Next.js application
RUN npm run build

# 2. Runner Stage: Create a minimal production image
FROM node:18-alpine AS runner
WORKDIR /app

# Set environment variables for production
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED 1

# Copy the standalone output from the builder stage
COPY --from=builder /app/.next/standalone ./
# Copy the public assets
COPY --from=builder /app/public ./public
# Copy the static assets (.next/static)
COPY --from=builder /app/.next/static ./.next/static

# Expose the port Next.js runs on
EXPOSE 3000

# Set the command to run the Next.js server
CMD ["node", "server.js"] 