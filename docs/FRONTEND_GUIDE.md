# Frontend Development Guide

## Tech Stack
- Next.js 14 (App Router)
- TypeScript (strict mode)
- Tailwind CSS
- shadcn/ui components
- TanStack Query for server state
- Zustand for client state (minimal — auth store only)

## Project Structure
```
frontend/src/
├── app/
│   ├── (auth)/
│   │   └── login/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx           # Sidebar + header + content
│   │   ├── dashboard/page.tsx   # Home dashboard
│   │   ├── users/
│   │   │   ├── page.tsx         # User list
│   │   │   └── [id]/page.tsx    # User detail/edit
│   │   ├── attendance/page.tsx
│   │   ├── leaves/page.tsx
│   │   ├── teams/page.tsx
│   │   ├── leads/page.tsx
│   │   ├── projects/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── tasks/page.tsx
│   └── (super-admin)/
│       ├── layout.tsx
│       ├── companies/page.tsx
│       ├── plans/page.tsx
│       └── features/page.tsx
├── components/
│   ├── ui/                  # shadcn components (button, input, dialog, etc.)
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   └── breadcrumbs.tsx
│   └── shared/
│       ├── data-table.tsx   # Reusable table with pagination, sorting, search
│       ├── status-badge.tsx
│       ├── empty-state.tsx
│       ├── loading-skeleton.tsx
│       ├── confirm-dialog.tsx
│       └── stats-card.tsx
├── lib/
│   ├── api-client.ts        # Axios instance with interceptors
│   ├── auth.ts              # Token management, refresh logic
│   ├── utils.ts             # cn(), formatDate(), formatCurrency()
│   └── constants.ts
├── hooks/
│   ├── use-auth.ts
│   ├── use-users.ts
│   ├── use-attendance.ts
│   └── use-leaves.ts
├── types/
│   ├── auth.ts
│   ├── user.ts
│   ├── attendance.ts
│   └── common.ts            # PaginatedResponse, ApiError, etc.
└── stores/
    └── auth-store.ts         # Zustand: current user, permissions, logout
```

## API Client Pattern
```typescript
// lib/api-client.ts
const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL });

// Request interceptor: attach access token
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const newToken = await refreshToken();
      error.config.headers.Authorization = `Bearer ${newToken}`;
      return api(error.config);
    }
    return Promise.reject(error);
  }
);
```

## TanStack Query Pattern
```typescript
// hooks/use-users.ts
export function useUsers(params: UserListParams) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => api.get('/users', { params }).then(r => r.data),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateUserInput) => api.post('/users', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}
```

## Component Standards
- Every page has: loading skeleton, error state, empty state
- Tables use the shared DataTable component (never raw HTML tables)
- Forms use react-hook-form + zod for validation
- All dates displayed in user's timezone
- All money amounts formatted with ₹ symbol
- Status badges use consistent color mapping across the app
- Modals for create/edit, drawers for detail views