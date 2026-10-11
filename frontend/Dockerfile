# syntax=docker/dockerfile:1.7

# 阶段 1：构建静态资源
FROM node:20-alpine AS build

WORKDIR /app

# 优先安装依赖，最大化缓存命中
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public

ARG VITE_BASE_PATH=/
ARG RELEASE_SHA=development
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
RUN npm run build
RUN printf '{"commit":"%s"}\n' "$RELEASE_SHA" > /app/dist/release.json

# 阶段 2：Nginx 托管静态文件 + 反向代理 /api
FROM nginx:1.27-alpine AS runtime

# 把构建产物替换默认站点根目录
COPY --from=build /app/dist /usr/share/nginx/html

# 自定义站点配置：/api 反代到 backend，关闭 proxy_buffering 以支持 SSE
ARG VITE_BASE_PATH=/
ARG BACKEND_HOST=backend
COPY nginx.conf /tmp/nginx.conf
RUN sed -e "s|__APP_BASE__|${VITE_BASE_PATH}|g" \
    -e "s|__APP_BASE_NO_SLASH__|${VITE_BASE_PATH%/}|g" \
    -e "s|__BACKEND_HOST__|${BACKEND_HOST}|g" \
    /tmp/nginx.conf > /etc/nginx/conf.d/default.conf && rm /tmp/nginx.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
