import type { ReactElement, ReactNode } from 'react';
import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { theme } from '../theme';

interface ProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string;
}

/** Render with Chakra, React Query (no retries) and a MemoryRouter. */
export function renderWithProviders(ui: ReactElement, { route = '/', ...options }: ProvidersOptions = {}): RenderResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    );
  }
  return render(ui, { wrapper: Wrapper, ...options });
}
