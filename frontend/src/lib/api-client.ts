import axios from 'axios'

/** Backend API client. In dev, Vite proxies `/api` to the FastAPI server. */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  headers: {
    Accept: 'application/json',
  },
})
