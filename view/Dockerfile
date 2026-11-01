FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
COPY packages/ ./packages/
COPY view/ ./view/
RUN npm install
RUN npm --prefix view run build

FROM nginx:alpine
COPY --from=build /app/view/dist/web /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
