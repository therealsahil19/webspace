import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { apiClient } from '@/lib/api'
import ManualRefreshPage from '../page'

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    triggerManualRefresh: jest.fn(),
  },
}))

describe('ManualRefreshPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should render refresh interface', () => {
    render(<ManualRefreshPage />)

    expect(screen.getByText('Manual Data Refresh')).toBeInTheDocument()
    expect(screen.getByText('Trigger an immediate refresh of launch data from all configured sources.')).toBeInTheDocument()
    expect(screen.getByText('Refresh Launch Data')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /start refresh/i })).toBeInTheDocument()
  })

  it('should display information about the refresh process', () => {
    render(<ManualRefreshPage />)

    expect(screen.getByText('About Manual Refresh')).toBeInTheDocument()
    expect(screen.getByText(/The refresh process runs in the background/)).toBeInTheDocument()
    expect(screen.getByText(/Data is collected from multiple sources/)).toBeInTheDocument()
  })

  it('should trigger refresh successfully', async () => {
    const mockResponse = {
      message: 'Refresh started successfully',
      task_id: 'task-123'
    }
    ;(apiClient.triggerManualRefresh as jest.Mock).mockResolvedValue(mockResponse)

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    expect(refreshButton).toBeDisabled()
    expect(screen.getByText('Refreshing Data...')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Refresh Started Successfully')).toBeInTheDocument()
      expect(screen.getByText('Refresh started successfully')).toBeInTheDocument()
      expect(screen.getByText('task-123')).toBeInTheDocument()
    })

    expect(apiClient.triggerManualRefresh).toHaveBeenCalledTimes(1)
  })

  it('should handle refresh failure', async () => {
    const errorMessage = 'Failed to start refresh'
    ;(apiClient.triggerManualRefresh as jest.Mock).mockRejectedValue(new Error(errorMessage))

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    await waitFor(() => {
      expect(screen.getByText('Refresh Failed')).toBeInTheDocument()
      expect(screen.getByText(errorMessage)).toBeInTheDocument()
    })
  })

  it('should show loading state during refresh', async () => {
    ;(apiClient.triggerManualRefresh as jest.Mock).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    )

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    expect(refreshButton).toBeDisabled()
    expect(screen.getByText('Refreshing Data...')).toBeInTheDocument()
    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument() // Loading spinner
  })

  it('should display refresh history when available', async () => {
    const mockResponse = {
      message: 'Refresh completed',
      task_id: 'task-456'
    }
    ;(apiClient.triggerManualRefresh as jest.Mock).mockResolvedValue(mockResponse)

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    await waitFor(() => {
      expect(screen.getByText('Refresh History')).toBeInTheDocument()
      expect(screen.getByText('Manual Refresh')).toBeInTheDocument()
      expect(screen.getByText('Started')).toBeInTheDocument()
    })
  })

  it('should show empty state for refresh history initially', () => {
    render(<ManualRefreshPage />)

    expect(screen.getByText('Refresh History')).toBeInTheDocument()
    expect(screen.getByText('No manual refreshes have been triggered yet.')).toBeInTheDocument()
  })

  it('should display failed refresh in history', async () => {
    ;(apiClient.triggerManualRefresh as jest.Mock).mockRejectedValue(new Error('Network error'))

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    await waitFor(() => {
      expect(screen.getByText('Failed')).toBeInTheDocument()
    })
  })

  it('should enable button after refresh completes', async () => {
    const mockResponse = {
      message: 'Refresh started',
      task_id: 'task-789'
    }
    ;(apiClient.triggerManualRefresh as jest.Mock).mockResolvedValue(mockResponse)

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    expect(refreshButton).toBeDisabled()

    await waitFor(() => {
      expect(refreshButton).not.toBeDisabled()
    })
  })

  it('should display timestamp for refresh history', async () => {
    const mockResponse = {
      message: 'Refresh started',
      task_id: 'task-999'
    }
    ;(apiClient.triggerManualRefresh as jest.Mock).mockResolvedValue(mockResponse)

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    fireEvent.click(refreshButton)

    await waitFor(() => {
      // Check that a timestamp is displayed (format may vary)
      const timestampRegex = /\d{1,2}\/\d{1,2}\/\d{4}/
      expect(screen.getByText(timestampRegex)).toBeInTheDocument()
    })
  })

  it('should clear error state on successful refresh', async () => {
    ;(apiClient.triggerManualRefresh as jest.Mock)
      .mockRejectedValueOnce(new Error('First error'))
      .mockResolvedValueOnce({ message: 'Success', task_id: 'task-success' })

    render(<ManualRefreshPage />)

    const refreshButton = screen.getByRole('button', { name: /start refresh/i })
    
    // First click - should fail
    fireEvent.click(refreshButton)

    await waitFor(() => {
      expect(screen.getByText('Refresh Failed')).toBeInTheDocument()
    })

    // Second click - should succeed
    fireEvent.click(refreshButton)

    await waitFor(() => {
      expect(screen.getByText('Refresh Started Successfully')).toBeInTheDocument()
      expect(screen.queryByText('Refresh Failed')).not.toBeInTheDocument()
    })
  })
})