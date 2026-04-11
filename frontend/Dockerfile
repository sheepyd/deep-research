FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app
RUN npm run build

EXPOSE 4173

CMD ["node", "server.mjs"]
