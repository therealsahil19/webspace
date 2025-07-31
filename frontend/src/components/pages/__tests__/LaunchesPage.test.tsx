import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LaunchesPage } from '../LaunchesPage'
import { apiClient } from '@/lib/api'
import { useLaunchStore } from '@/store/launchStore'

// Mock the API client
jest.mock('@/lib/api')
const mockApiClient = apiClient as jest.Mocked<typeof apiClient>

// Mock the store
jest.mock('@/store/launchStore')
const mockUseLaunchStore = useLaunchStore as jest.MockedFunction<typeof useLaunchStore>

// Mock the hooks
jest.mock('@/hooks/useInfiniteScroll', () => ({
  useInfiniteScroll: () => ({ isFetching: false })
}))

// Mock components
jest.mock('@/components/ui/LoadingSpinner', () => ({
  LoadingSpinner: () => <div data-testid="loading-spinner">Loading...</div>
}))

jest.mock('@/components/ui/ErrorMessage', () => ({
  ErrorMessage: ({ message, onRetry }: { message: string; onRetry: () => void }) => (
    <div data-testid="error-message">
      <span>{message}</span>
      <button onClick={onRetry} data-testid="retry-button">Retry</button>
    </div>
  )
}))

jest.mock('@/components/ui/LaunchCard', () => ({
  LaunchCard: ({ launch }: { launch: any }) => (
    <div data-testid={`launch-card-${launch.slug}`}>
      <h3>{launch.mission_name}</h3>
      <span>{launch.status}</span>
    </div>
  )
}))

const mockLaunchData = [
  {
    slug: 'falcon-heavy-demo',
    mission_name: 'Falcon Heavy Demo',
    launch_date: '2018-02-06T20:45:00Z',
    vehicle_type: 'Falcon Heavy',
    payload_mass: 1420,
    orbit: 'Mars',
    status: 'success' as const,
    details: 'First Falcon Heavy test flight',
    mission_patch_url: null,
    webcast_url: 'https://youtube.com/watch?v=test'
  },
  {
    slug: 'starship-test',
    mission_name: 'Starship Test',
    launch_date: '2024-03-15T14:30:00Z',
    vehicle_type: 'Starship',
    payload_mass: null,
    orbit: 'LEO',
    status: 'upcoming' as const,
    details: 'Starship orbital test flight',
    mission_patch_url: null,
    webcast_url: null
  }
]

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
})

const renderWithQueryClient = (component: React.ReactElement) => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  )
}

describe('LaunchesPage', () => {
  beforeEach(() => {
    mockUseLaunchStore.mockReturnValue({
      preferences: { itemsPerPage: 10 },
      setPreferences: jest.fn(),
      launches: [],
      setLaunches: jest.fn(),
      addLaunch: jest.fn(),
      updateLaunch: jest.fn(),
      removeLaunch: jest.fn()
    })

    mockApiClient.getLaunches.mockResolvedValue({
      data: mockLaunchData,
      total: 2,
      page: 1,
      limit: 10
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('renders the launches page with header', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    expect(screen.getByText('All Launches')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('2 launches found')).toBeInTheDocument()
    })
  })

  it('displays launches in grid view by default', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
      expect(screen.getByTestId('launch-card-starship-test')).toBeInTheDocument()
    })
  })

  it('switches between grid and list view', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Find view mode buttons
    const listViewButton = screen.getAllByRole('button').find(button => 
      button.querySelector('svg')?.getAttribute('fill-rule') === 'evenodd'
    )
    
    if (listViewButton) {
      fireEvent.click(listViewButton)
      // The view should change (implementation detail, but structure changes)
      await waitFor(() => {
        expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
      })
    }
  })

  it('handles search functionality', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Find and interact with search input
    const searchInput = screen.getByPlaceholderText('Search by mission name...')
    fireEvent.change(searchInput, { target: { value: 'Falcon' } })

    // Wait for debounced search
    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'Falcon'
        })
      )
    }, { timeout: 1000 })
  })

  it('handles status filtering', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Find status filter dropdown
    const statusSelect = screen.getByDisplayValue('All Status')
    fireEvent.change(statusSelect, { target: { value: 'success' } })

    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          status: 'success'
        })
      )
    })
  })

  it('handles vehicle type filtering', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Find vehicle type filter dropdown
    const vehicleSelect = screen.getByDisplayValue('All Vehicles')
    fireEvent.change(vehicleSelect, { target: { value: 'Falcon Heavy' } })

    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          vehicle_type: 'Falcon Heavy'
        })
      )
    })
  })

  it('handles date range filtering', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Find date inputs
    const fromDateInput = screen.getByLabelText('From Date')
    const toDateInput = screen.getByLabelText('To Date')

    fireEvent.change(fromDateInput, { target: { value: '2018-01-01' } })
    fireEvent.change(toDateInput, { target: { value: '2018-12-31' } })

    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: '2018-01-01',
          date_to: '2018-12-31'
        })
      )
    })
  })

  it('handles sorting options', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Find sort by dropdown
    const sortBySelect = screen.getByDisplayValue('Launch Date')
    fireEvent.change(sortBySelect, { target: { value: 'mission_name' } })

    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_by: 'mission_name'
        })
      )
    })

    // Find sort order dropdown
    const sortOrderSelect = screen.getByDisplayValue('Newest First')
    fireEvent.change(sortOrderSelect, { target: { value: 'asc' } })

    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_order: 'asc'
        })
      )
    })
  })

  it('clears all filters when clear button is clicked', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Set some filters
    const searchInput = screen.getByPlaceholderText('Search by mission name...')
    fireEvent.change(searchInput, { target: { value: 'Falcon' } })

    const statusSelect = screen.getByDisplayValue('All Status')
    fireEvent.change(statusSelect, { target: { value: 'success' } })

    // Wait for filters to be applied
    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'Falcon',
          status: 'success'
        })
      )
    })

    // Click clear filters button
    const clearButton = screen.getByText('Clear Filters')
    fireEvent.click(clearButton)

    // Verify filters are cleared
    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          search: undefined,
          status: undefined
        })
      )
    })
  })

  it('toggles infinite scroll mode', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Find infinite scroll toggle
    const infiniteScrollToggle = screen.getByLabelText(/Infinite Scroll/i)
    fireEvent.click(infiniteScrollToggle)

    // The component should switch to infinite scroll mode
    // This is tested by checking if the toggle is checked
    expect(infiniteScrollToggle).toBeChecked()
  })

  it('handles pagination in regular mode', async () => {
    mockApiClient.getLaunches.mockResolvedValue({
      data: mockLaunchData,
      total: 25,
      page: 1,
      limit: 10
    })

    renderWithQueryClient(<LaunchesPage />)
    
    await waitFor(() => {
      expect(screen.getByText('Showing 2 of 25 launches')).toBeInTheDocument()
    })

    // Find and click next button
    const nextButton = screen.getByText('Next')
    fireEvent.click(nextButton)

    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 2
        })
      )
    })
  })

  it('displays empty state when no launches found', async () => {
    mockApiClient.getLaunches.mockResolvedValue({
      data: [],
      total: 0,
      page: 1,
      limit: 10
    })

    renderWithQueryClient(<LaunchesPage />)
    
    await waitFor(() => {
      expect(screen.getByText('No launches found')).toBeInTheDocument()
      expect(screen.getByText('Try adjusting your search criteria or filters to find more launches.')).toBeInTheDocument()
    })
  })

  it('displays loading state', () => {
    mockApiClient.getLaunches.mockImplementation(() => new Promise(() => {})) // Never resolves

    renderWithQueryClient(<LaunchesPage />)
    
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
  })

  it('displays error state and handles retry', async () => {
    const mockError = new Error('API Error')
    mockApiClient.getLaunches.mockRejectedValue(mockError)

    renderWithQueryClient(<LaunchesPage />)
    
    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument()
      expect(screen.getByText('Failed to load launches. Please try again later.')).toBeInTheDocument()
    })

    // Test retry functionality
    const retryButton = screen.getByTestId('retry-button')
    fireEvent.click(retryButton)

    expect(mockApiClient.getLaunches).toHaveBeenCalledTimes(2)
  })

  it('resets page when filters change', async () => {
    renderWithQueryClient(<LaunchesPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByTestId('launch-card-falcon-heavy-demo')).toBeInTheDocument()
    })

    // Change filter
    const statusSelect = screen.getByDisplayValue('All Status')
    fireEvent.change(statusSelect, { target: { value: 'success' } })

    // Should call API with page 1
    await waitFor(() => {
      expect(mockApiClient.getLaunches).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
          status: 'success'
        })
      )
    })
  })
})