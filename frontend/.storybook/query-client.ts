import { QueryClient } from "@tanstack/react-query";

export const storyQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: Infinity,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});
