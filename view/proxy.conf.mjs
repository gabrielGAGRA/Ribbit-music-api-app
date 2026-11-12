// view/proxy.conf.mjs
const target = process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000';

export default {
  '/api': {
    target,
    secure: false,
    changeOrigin: true,
  },
};
