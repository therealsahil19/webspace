import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HomePage } from '../HomePage'

// Mock the API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    getUpcomingLaunches: jest.fn(),
  },
}))

// Mock Next.js Link component
jest.mock('next/link', () => {
  return function MockLink({ children, href }: { children: React.ReactNode; href: string }) {
    return <a href={href}>{children}</a>
  }
})

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

const renderWithQueryClient = (component: React.ReactElement) => {
  const testQueryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={testQueryClient}>
      {component}
    </QueryClientProvider>
  )
}

describe('HomePage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders the hero section correctly', () => {
    renderWithQueryClient(<HomePage />)
    
    expect(screen.getByText('SpaceX Launch Tracker')).toBeInTheDocument()
    expect(screen.getByText(/Stay up-to-date with the latest SpaceX launches/)).toBeInTheDocument()
    expect(screen.getByText('View All Launches')).toBeInTheDocument()
    expect(screen.getByText('Upcoming Launches')).toBeInTheDocument()
  })

  it('renders the stats section', () => {
    renderWithQueryClient(<HomePage />)
    
    expect(screen.getByText('Mission Statistics')).toBeInTheDocument()
    expect(screen.getByText('200+')).toBeInTheDocument()
    expect(screen.getByText('Total Launches')).toBeInTheDocument()
    expect(screen.getByText('95%')).toBeInTheDocument()
    expect(screen.getByText('Success Rate')).toBeInTheDocument()
    expect(screen.getByText('150+')).toBeInTheDocument()
    expect(screen.getByText('Successful Landings')).toBeInTheDocument()
  })

  it('shows loading spinner while fetching data', () => {
    renderWithQueryClient(<HomePage />)
    
    // The loading spinner should be present initially
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})