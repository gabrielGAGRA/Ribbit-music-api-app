const apiTarget = process.env.RIBBIT_API_URL ?? 'http://127.0.0.1:8000';

const proxy = {
  '/api': {
    target: apiTarget,
    changeOrigin: true,
    secure: false,
  },
};

export default {
  server: { proxy },
  preview: { proxy },
};
