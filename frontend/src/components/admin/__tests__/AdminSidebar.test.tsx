import { render, screen } from '@testing-library/react'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { AdminSidebar } from '../AdminSidebar'

// Mock Next.js navigation
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(),
}))

// Mock auth store
jest.mock('@/store/authStore', () => ({
  useAuthStore: jest.fn(),
}))

describe('AdminSidebar', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(usePathname as jest.Mock).mockReturnValue('/admin/dashboard')
    ;(useAuthStore as jest.Mock).mockReturnValue({
      user: {
        id: '1',
        username: 'admin',
        role: 'admin',
      },
    })
  })

  it('should render sidebar with navigation items', () => {
    render(<AdminSidebar />)

    expect(screen.getByText('SpaceX Admin')).toBeInTheDocument()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('System Health')).toBeInTheDocument()
    expect(screen.getByText('Data Conflicts')).toBeInTheDocument()
    expect(screen.getByText('System Logs')).toBeInTheDocument()
    expect(screen.getByText('Manual Refresh')).toBeInTheDocument()
  })

  it('should display user information', () => {
    render(<AdminSidebar />)

    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument() // role
    expect(screen.getByText('A')).toBeInTheDocument() // avatar initial
  })

  it('should highlight active navigation item', () => {
    ;(usePathname as jest.Mock).mockReturnValue('/admin/health')

    render(<AdminSidebar />)

    const healthLink = screen.getByText('System Health').closest('a')
    const dashboardLink = screen.getByText('Dashboard').closest('a')

    expect(healthLink).toHaveClass('bg-blue-100', 'text-blue-700')
    expect(dashboardLink).not.toHaveClass('bg-blue-100', 'text-blue-700')
  })

  it('should render correct navigation links', () => {
    render(<AdminSidebar />)

    const dashboardLink = screen.getByText('Dashboard').closest('a')
    const healthLink = screen.getByText('System Health').closest('a')
    const conflictsLink = screen.getByText('Data Conflicts').closest('a')
    const logsLink = screen.getByText('System Logs').closest('a')
    const refreshLink = screen.getByText('Manual Refresh').closest('a')

    expect(dashboardLink).toHaveAttribute('href', '/admin/dashboard')
    expect(healthLink).toHaveAttribute('href', '/admin/health')
    expect(conflictsLink).toHaveAttribute('href', '/admin/conflicts')
    expect(logsLink).toHaveAttribute('href', '/admin/logs')
    expect(refreshLink).toHaveAttribute('href', '/admin/refresh')
  })

  it('should handle user with no username', () => {
    ;(useAuthStore as jest.Mock).mockReturnValue({
      user: {
        id: '1',
        username: null,
        role: 'admin',
      },
    })

    render(<AdminSidebar />)

    expect(screen.getByText('Admin')).toBeInTheDocument()
    expect(screen.getByText('A')).toBeInTheDocument() // default avatar initial
  })

  it('should handle missing user', () => {
    ;(useAuthStore as jest.Mock).mockReturnValue({
      user: null,
    })

    render(<AdminSidebar />)

    expect(screen.getByText('Admin')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument() // default role
    expect(screen.getByText('A')).toBeInTheDocument() // default avatar initial
  })

  it('should render all navigation icons', () => {
    render(<AdminSidebar />)

    // Check that SVG icons are present for each navigation item
    const svgElements = screen.getAllByRole('img', { hidden: true })
    expect(svgElements.length).toBeGreaterThan(0)
  })

  it('should apply correct styling for non-active items', () => {
    ;(usePathname as jest.Mock).mockReturnValue('/admin/dashboard')

    render(<AdminSidebar />)

    const healthLink = screen.getByText('System Health').closest('a')
    expect(healthLink).toHaveClass('text-gray-700', 'hover:bg-gray-100')
    expect(healthLink).not.toHaveClass('bg-blue-100', 'text-blue-700')
  })
})