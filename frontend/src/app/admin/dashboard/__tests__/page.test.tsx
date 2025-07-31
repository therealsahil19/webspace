import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { apiClient } from '@/lib/api'
import AdminDashboardPage from '../page'

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    getSystemStats: jest.fn(),
  },
}))

const mockStats = {
  total_launches: 150,
  upcoming_launches: 5,
  last_scrape: '2024-01-15T10:30:00Z',
  data_sources: [
    {
      name: 'SpaceX API',
      last_successful_scrape: '2024-01-15T10:30:00Z',
      success_rate: 0.95,
      status: 'healthy'
    },
    {
      name: 'NASA API',
      last_successful_scrape: '2024-01-15T09:45:00Z',
      success_rate: 0.88,
      status: 'warning'
    },
    {
      name: 'Wikipedia',
      last_successful_scrape: '2024-01-15T08:15:00Z',
      success_rate: 0.72,
      status: 'error'
    }
  ],
  conflicts: {
    total: 12,
    unresolved: 3
  }
}

describe('AdminDashboardPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(apiClient.getSystemStats as jest.Mock).mockResolvedValue(mockStats)
  })

  it('should render loading state initially', () => {
    ;(apiClient.getSystemStats as jest.Mock).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(<AdminDashboardPage />)

    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })

  it('should render dashboard with system stats', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument() // total launches
      expect(screen.getByText('5')).toBeInTheDocument() // upcoming launches
      expect(screen.getByText('12')).toBeInTheDocument() // total conflicts
      expect(screen.getByText('3')).toBeInTheDocument() // unresolved conflicts
    })

    expect(screen.getByText('Total Launches')).toBeInTheDocument()
    expect(screen.getByText('Upcoming Launches')).toBeInTheDocument()
    expect(screen.getByText('Total Conflicts')).toBeInTheDocument()
    expect(screen.getByText('Unresolved Conflicts')).toBeInTheDocument()
  })

  it('should display last scrape information', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Last Data Scrape')).toBeInTheDocument()
      expect(screen.getByText(/1\/15\/2024/)).toBeInTheDocument()
    })
  })

  it('should render data sources status', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Data Sources Status')).toBeInTheDocument()
      expect(screen.getByText('SpaceX API')).toBeInTheDocument()
      expect(screen.getByText('NASA API')).toBeInTheDocument()
      expect(screen.getByText('Wikipedia')).toBeInTheDocument()
    })

    // Check success rates
    expect(screen.getByText('95.0%')).toBeInTheDocument()
    expect(screen.getByText('88.0%')).toBeInTheDocument()
    expect(screen.getByText('72.0%')).toBeInTheDocument()
  })

  it('should display correct status indicators for data sources', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      const healthyIndicator = screen.getByText('SpaceX API').closest('div')?.querySelector('.bg-green-400')
      const warningIndicator = screen.getByText('NASA API').closest('div')?.querySelector('.bg-yellow-400')
      const errorIndicator = screen.getByText('Wikipedia').closest('div')?.querySelector('.bg-red-400')

      expect(healthyIndicator).toBeInTheDocument()
      expect(warningIndicator).toBeInTheDocument()
      expect(errorIndicator).toBeInTheDocument()
    })
  })

  it('should handle API error', async () => {
    const errorMessage = 'Failed to load system stats'
    ;(apiClient.getSystemStats as jest.Mock).mockRejectedValue(new Error(errorMessage))

    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument()
      expect(screen.getByText(errorMessage)).toBeInTheDocument()
    })
  })

  it('should allow retry on error', async () => {
    ;(apiClient.getSystemStats as jest.Mock)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockStats)

    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })

    const retryButton = screen.getByText('Try again')
    fireEvent.click(retryButton)

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument()
    })

    expect(apiClient.getSystemStats).toHaveBeenCalledTimes(2)
  })

  it('should handle empty stats gracefully', async () => {
    ;(apiClient.getSystemStats as jest.Mock).mockResolvedValue(null)

    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('No data available')).toBeInTheDocument()
    })
  })

  it('should format dates correctly', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      // Check that dates are formatted in a readable way
      const dateElements = screen.getAllByText(/1\/15\/2024/)
      expect(dateElements.length).toBeGreaterThan(0)
    })
  })

  it('should call API on component mount', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      expect(apiClient.getSystemStats).toHaveBeenCalledTimes(1)
    })
  })

  it('should display overview cards with correct icons', async () => {
    render(<AdminDashboardPage />)

    await waitFor(() => {
      // Check that all overview cards are rendered
      const cards = screen.getAllByRole('definition')
      expect(cards).toHaveLength(4)
    })
  })
})