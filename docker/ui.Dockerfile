FROM node:20-alpine AS builder

WORKDIR /app

COPY ui/groundedagent-ui/package*.json /app/
RUN npm install

COPY ui/groundedagent-ui /app

RUN npm run build

FROM nginx:1.27-alpine

COPY ui/groundedagent-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/groundedagent-ui/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]