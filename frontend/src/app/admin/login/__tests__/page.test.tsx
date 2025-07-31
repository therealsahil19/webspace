import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import AdminLoginPage from '../page'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

// Mock auth store
jest.mock('@/store/authStore', () => ({
  useAuthStore: jest.fn(),
}))

const mockPush = jest.fn()
const mockLogin = jest.fn()
const mockClearError = jest.fn()

describe('AdminLoginPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
    ;(useAuthStore as jest.Mock).mockReturnValue({
      login: mockLogin,
      isLoading: false,
      error: null,
      isAuthenticated: false,
      clearError: mockClearError,
    })
  })

  it('should render login form', () => {
    render(<AdminLoginPage />)

    expect(screen.getByText('Admin Login')).toBeInTheDocument()
    expect(screen.getByText('Access the SpaceX Launch Tracker admin dashboard')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('should redirect to dashboard if already authenticated', () => {
    ;(useAuthStore as jest.Mock).mockReturnValue({
      login: mockLogin,
      isLoading: false,
      error: null,
      isAuthenticated: true,
      clearError: mockClearError,
    })

    render(<AdminLoginPage />)

    expect(mockPush).toHaveBeenCalledWith('/admin/dashboard')
  })

  it('should clear errors on mount', () => {
    render(<AdminLoginPage />)

    expect(mockClearError).toHaveBeenCalled()
  })

  it('should handle form submission with valid credentials', async () => {
    mockLogin.mockResolvedValueOnce(undefined)

    render(<AdminLoginPage />)

    const usernameInput = screen.getByPlaceholderText('Username')
    const passwordInput = screen.getByPlaceholderText('Password')
    const submitButton = screen.getByRole('button', { name: 'Sign in' })

    fireEvent.change(usernameInput, { target: { value: 'admin' } })
    fireEvent.change(passwordInput, { target: { value: 'password' } })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'password')
    })

    expect(mockPush).toHaveBeenCalledWith('/admin/dashboard')
  })

  it('should handle login failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'))

    render(<AdminLoginPage />)

    const usernameInput = screen.getByPlaceholderText('Username')
    const passwordInput = screen.getByPlaceholderText('Password')
    const submitButton = screen.getByRole('button', { name: 'Sign in' })

    fireEvent.change(usernameInput, { target: { value: 'admin' } })
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'wrongpassword')
    })

    expect(mockPush).not.toHaveBeenCalled()
  })

  it('should display error message when login fails', () => {
    ;(useAuthStore as jest.Mock).mockReturnValue({
      login: mockLogin,
      isLoading: false,
      error: 'Invalid credentials',
      isAuthenticated: false,
      clearError: mockClearError,
    })

    render(<AdminLoginPage />)

    expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
  })

  it('should show loading state during login', () => {
    ;(useAuthStore as jest.Mock).mockReturnValue({
      login: mockLogin,
      isLoading: true,
      error: null,
      isAuthenticated: false,
      clearError: mockClearError,
    })

    render(<AdminLoginPage />)

    expect(screen.getByText('Signing in...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
  })

  it('should disable submit button when fields are empty', () => {
    render(<AdminLoginPage />)

    const submitButton = screen.getByRole('button', { name: 'Sign in' })
    expect(submitButton).toBeDisabled()
  })

  it('should enable submit button when both fields are filled', () => {
    render(<AdminLoginPage />)

    const usernameInput = screen.getByPlaceholderText('Username')
    const passwordInput = screen.getByPlaceholderText('Password')
    const submitButton = screen.getByRole('button', { name: 'Sign in' })

    fireEvent.change(usernameInput, { target: { value: 'admin' } })
    fireEvent.change(passwordInput, { target: { value: 'password' } })

    expect(submitButton).not.toBeDisabled()
  })

  it('should not submit form with empty fields', () => {
    render(<AdminLoginPage />)

    const submitButton = screen.getByRole('button', { name: 'Sign in' })
    fireEvent.click(submitButton)

    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('should disable inputs during loading', () => {
    ;(useAuthStore as jest.Mock).mockReturnValue({
      login: mockLogin,
      isLoading: true,
      error: null,
      isAuthenticated: false,
      clearError: mockClearError,
    })

    render(<AdminLoginPage />)

    const usernameInput = screen.getByPlaceholderText('Username')
    const passwordInput = screen.getByPlaceholderText('Password')

    expect(usernameInput).toBeDisabled()
    expect(passwordInput).toBeDisabled()
  })
})