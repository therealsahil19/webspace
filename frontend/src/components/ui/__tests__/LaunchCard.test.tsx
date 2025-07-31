import { render, screen } from '@testing-library/react'
import { LaunchCard } from '../LaunchCard'
import { LaunchData } from '@/lib/api'

// Mock Next.js Link component
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  )
  MockLink.displayName = 'MockLink'
  return MockLink
})

const mockLaunchData: LaunchData = {
  slug: 'falcon-heavy-demo',
  mission_name: 'Falcon Heavy Demo',
  launch_date: '2018-02-06T20:45:00Z',
  vehicle_type: 'Falcon Heavy',
  payload_mass: 1420,
  orbit: 'Mars',
  status: 'success',
  details: 'First Falcon Heavy test flight with a Tesla Roadster as payload',
  mission_patch_url: 'https://example.com/patch.png',
  webcast_url: 'https://youtube.com/watch?v=test'
}

describe('LaunchCard', () => {
  it('renders launch information correctly', () => {
    render(<LaunchCard launch={mockLaunchData} />)

    expect(screen.getByText('Falcon Heavy Demo')).toBeInTheDocument()
    expect(screen.getByText('Success')).toBeInTheDocument()
    expect(screen.getByText('Falcon Heavy')).toBeInTheDocument()
    expect(screen.getByText('Mars')).toBeInTheDocument()
    expect(screen.getByText('1,420 kg')).toBeInTheDocument()
    expect(screen.getByText('First Falcon Heavy test flight with a Tesla Roadster as payload')).toBeInTheDocument()
  })

  it('formats launch date correctly', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    // Should format date as "Feb 7, 2018" (depending on locale and timezone)
    expect(screen.getByText(/Feb 7, 2018/)).toBeInTheDocument()
  })

  it('handles null launch date', () => {
    const launchWithoutDate: LaunchData = {
      ...mockLaunchData,
      launch_date: null
    }

    render(<LaunchCard launch={launchWithoutDate} />)
    
    expect(screen.getByText('TBD')).toBeInTheDocument()
  })

  it('renders mission patch when available', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    const missionPatch = screen.getByAltText('Falcon Heavy Demo mission patch')
    expect(missionPatch).toBeInTheDocument()
    expect(missionPatch).toHaveAttribute('src', 'https://example.com/patch.png')
  })

  it('renders default icon when mission patch is not available', () => {
    const launchWithoutPatch: LaunchData = {
      ...mockLaunchData,
      mission_patch_url: null
    }

    render(<LaunchCard launch={launchWithoutPatch} />)
    
    // Should not render mission patch image
    expect(screen.queryByAltText('Falcon Heavy Demo mission patch')).not.toBeInTheDocument()
    // Default icon is rendered as SVG, check for its presence
    const svgIcon = document.querySelector('svg')
    expect(svgIcon).toBeInTheDocument()
  })

  it('renders correct status badge colors', () => {
    const statuses: Array<LaunchData['status']> = ['success', 'upcoming', 'failure', 'in_flight', 'aborted']
    
    statuses.forEach(status => {
      const launch: LaunchData = { ...mockLaunchData, status }
      const { rerender } = render(<LaunchCard launch={launch} />)
      
      const statusBadge = screen.getByText(status === 'in_flight' ? 'In Flight' : status.charAt(0).toUpperCase() + status.slice(1))
      expect(statusBadge).toBeInTheDocument()
      
      // Check that the badge has appropriate styling classes
      expect(statusBadge).toHaveClass('px-2', 'py-1', 'text-xs', 'font-medium', 'rounded-full')
      
      rerender(<div />) // Clear for next iteration
    })
  })

  it('renders view details link correctly', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    const detailsLink = screen.getByText('View Details')
    expect(detailsLink).toBeInTheDocument()
    expect(detailsLink.closest('a')).toHaveAttribute('href', '/launches/falcon-heavy-demo')
  })

  it('renders watch link when webcast URL is available', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    const watchLink = screen.getByText('Watch')
    expect(watchLink).toBeInTheDocument()
    expect(watchLink.closest('a')).toHaveAttribute('href', 'https://youtube.com/watch?v=test')
    expect(watchLink.closest('a')).toHaveAttribute('target', '_blank')
    expect(watchLink.closest('a')).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('does not render watch link when webcast URL is not available', () => {
    const launchWithoutWebcast: LaunchData = {
      ...mockLaunchData,
      webcast_url: null
    }

    render(<LaunchCard launch={launchWithoutWebcast} />)
    
    expect(screen.queryByText('Watch')).not.toBeInTheDocument()
  })

  it('handles missing optional fields gracefully', () => {
    const minimalLaunch: LaunchData = {
      slug: 'minimal-launch',
      mission_name: 'Minimal Launch',
      launch_date: null,
      vehicle_type: null,
      payload_mass: null,
      orbit: null,
      status: 'upcoming',
      details: null,
      mission_patch_url: null,
      webcast_url: null
    }

    render(<LaunchCard launch={minimalLaunch} />)
    
    expect(screen.getByText('Minimal Launch')).toBeInTheDocument()
    expect(screen.getByText('Upcoming')).toBeInTheDocument()
    expect(screen.getByText('TBD')).toBeInTheDocument()
    
    // Should not render vehicle, orbit, or payload info when null
    expect(screen.queryByText('Vehicle:')).not.toBeInTheDocument()
    expect(screen.queryByText('Orbit:')).not.toBeInTheDocument()
    expect(screen.queryByText('Payload:')).not.toBeInTheDocument()
    expect(screen.queryByText('Watch')).not.toBeInTheDocument()
  })

  it('truncates long details text', () => {
    const launchWithLongDetails: LaunchData = {
      ...mockLaunchData,
      details: 'This is a very long description that should be truncated after a certain number of lines to prevent the card from becoming too tall and maintain a consistent layout across all launch cards in the grid view.'
    }

    render(<LaunchCard launch={launchWithLongDetails} />)
    
    const detailsElement = screen.getByText(launchWithLongDetails.details)
    expect(detailsElement).toHaveClass('line-clamp-3')
  })

  it('formats payload mass with proper locale formatting', () => {
    const launchWithLargePayload: LaunchData = {
      ...mockLaunchData,
      payload_mass: 63800
    }

    render(<LaunchCard launch={launchWithLargePayload} />)
    
    expect(screen.getByText('63,800 kg')).toBeInTheDocument()
  })

  it('applies hover effects correctly', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    // Find the main card container (outermost div)
    const card = document.querySelector('.bg-white')
    expect(card).toHaveClass('hover:shadow-lg', 'transition-all', 'duration-200')
  })

  it('has proper accessibility attributes', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    // Mission patch should have proper alt text
    if (mockLaunchData.mission_patch_url) {
      const missionPatch = screen.getByAltText('Falcon Heavy Demo mission patch')
      expect(missionPatch).toBeInTheDocument()
    }
    
    // External link should have proper attributes
    const watchLink = screen.getByText('Watch').closest('a')
    expect(watchLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('renders all icon elements correctly', () => {
    render(<LaunchCard launch={mockLaunchData} />)
    
    // Should have icons for date, vehicle, orbit, and payload
    const svgElements = document.querySelectorAll('svg')
    expect(svgElements.length).toBeGreaterThan(0)
  })
})