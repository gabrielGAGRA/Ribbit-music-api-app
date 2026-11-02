FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
COPY angular.json tsconfig.json ./
COPY view/ ./view/
RUN npm install
RUN npx ng build

FROM nginx:alpine
COPY --from=build /app/view/dist/web /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
