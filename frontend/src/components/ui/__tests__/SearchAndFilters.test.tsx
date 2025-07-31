import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SearchAndFilters, FilterOptions } from '../SearchAndFilters'

// Mock the useDebounce hook
jest.mock('@/hooks/useDebounce', () => ({
  useDebounce: (value: string, delay: number) => value // Return immediately for testing
}))

const defaultFilters: FilterOptions = {
  search: '',
  status: '',
  vehicleType: '',
  dateRange: { start: '', end: '' },
  sortBy: 'launch_date',
  sortOrder: 'desc'
}

const mockVehicleTypes = ['Falcon 9', 'Falcon Heavy', 'Starship']

describe('SearchAndFilters', () => {
  const mockOnFiltersChange = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders all filter controls', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    expect(screen.getByPlaceholderText('Search by mission name...')).toBeInTheDocument()
    expect(screen.getByDisplayValue('All Status')).toBeInTheDocument()
    expect(screen.getByDisplayValue('All Vehicles')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Launch Date')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Newest First')).toBeInTheDocument()
    expect(screen.getByLabelText('From Date')).toBeInTheDocument()
    expect(screen.getByLabelText('To Date')).toBeInTheDocument()
  })

  it('handles search input changes', async () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const searchInput = screen.getByPlaceholderText('Search by mission name...')
    fireEvent.change(searchInput, { target: { value: 'Falcon' } })

    await waitFor(() => {
      expect(mockOnFiltersChange).toHaveBeenCalledWith({
        ...defaultFilters,
        search: 'Falcon'
      })
    })
  })

  it('handles status filter changes', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const statusSelect = screen.getByDisplayValue('All Status')
    fireEvent.change(statusSelect, { target: { value: 'success' } })

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      status: 'success'
    })
  })

  it('handles vehicle type filter changes', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const vehicleSelect = screen.getByDisplayValue('All Vehicles')
    fireEvent.change(vehicleSelect, { target: { value: 'Falcon 9' } })

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      vehicleType: 'Falcon 9'
    })
  })

  it('renders vehicle types in dropdown', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const vehicleSelect = screen.getByDisplayValue('All Vehicles')
    
    // Check that all vehicle types are present as options
    mockVehicleTypes.forEach(vehicle => {
      expect(screen.getByRole('option', { name: vehicle })).toBeInTheDocument()
    })
  })

  it('handles sort by changes', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const sortBySelect = screen.getByDisplayValue('Launch Date')
    fireEvent.change(sortBySelect, { target: { value: 'mission_name' } })

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortBy: 'mission_name'
    })
  })

  it('handles sort order changes', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const sortOrderSelect = screen.getByDisplayValue('Newest First')
    fireEvent.change(sortOrderSelect, { target: { value: 'asc' } })

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortOrder: 'asc'
    })
  })

  it('handles date range changes', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const fromDateInput = screen.getByLabelText('From Date')
    const toDateInput = screen.getByLabelText('To Date')

    fireEvent.change(fromDateInput, { target: { value: '2023-01-01' } })
    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      dateRange: { start: '2023-01-01', end: '' }
    })

    fireEvent.change(toDateInput, { target: { value: '2023-12-31' } })
    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      dateRange: { start: '', end: '2023-12-31' }
    })
  })

  it('shows clear filters button when filters are active', () => {
    const filtersWithSearch: FilterOptions = {
      ...defaultFilters,
      search: 'Falcon'
    }

    render(
      <SearchAndFilters
        filters={filtersWithSearch}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    expect(screen.getByText('Clear Filters')).toBeInTheDocument()
  })

  it('hides clear filters button when no filters are active', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    expect(screen.queryByText('Clear Filters')).not.toBeInTheDocument()
  })

  it('clears all filters when clear button is clicked', () => {
    const filtersWithMultipleValues: FilterOptions = {
      search: 'Falcon',
      status: 'success',
      vehicleType: 'Falcon 9',
      dateRange: { start: '2023-01-01', end: '2023-12-31' },
      sortBy: 'mission_name',
      sortOrder: 'asc'
    }

    render(
      <SearchAndFilters
        filters={filtersWithMultipleValues}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    const clearButton = screen.getByText('Clear Filters')
    fireEvent.click(clearButton)

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      search: '',
      status: '',
      vehicleType: '',
      dateRange: { start: '', end: '' },
      sortBy: 'launch_date',
      sortOrder: 'desc'
    })
  })

  it('clears search input when X button is clicked', () => {
    const filtersWithSearch: FilterOptions = {
      ...defaultFilters,
      search: 'Falcon'
    }

    render(
      <SearchAndFilters
        filters={filtersWithSearch}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    // Find the clear search button (X icon)
    const clearSearchButton = screen.getByRole('button')
    fireEvent.click(clearSearchButton)

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      search: ''
    })
  })

  it('disables controls when loading', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
        isLoading={true}
      />
    )

    expect(screen.getByPlaceholderText('Search by mission name...')).toBeDisabled()
    expect(screen.getByDisplayValue('All Status')).toBeDisabled()
    expect(screen.getByDisplayValue('All Vehicles')).toBeDisabled()
    expect(screen.getByDisplayValue('Launch Date')).toBeDisabled()
    expect(screen.getByDisplayValue('Newest First')).toBeDisabled()
    expect(screen.getByLabelText('From Date')).toBeDisabled()
    expect(screen.getByLabelText('To Date')).toBeDisabled()
  })

  it('displays current filter values correctly', () => {
    const activeFilters: FilterOptions = {
      search: 'Starship',
      status: 'upcoming',
      vehicleType: 'Starship',
      dateRange: { start: '2024-01-01', end: '2024-12-31' },
      sortBy: 'mission_name',
      sortOrder: 'asc'
    }

    render(
      <SearchAndFilters
        filters={activeFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={mockVehicleTypes}
      />
    )

    expect(screen.getByDisplayValue('Starship')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Upcoming')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Mission Name')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Oldest First')).toBeInTheDocument()
    
    const fromDateInput = screen.getByLabelText('From Date') as HTMLInputElement
    const toDateInput = screen.getByLabelText('To Date') as HTMLInputElement
    expect(fromDateInput.value).toBe('2024-01-01')
    expect(toDateInput.value).toBe('2024-12-31')
  })

  it('handles empty vehicle types array', () => {
    render(
      <SearchAndFilters
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        vehicleTypes={[]}
      />
    )

    const vehicleSelect = screen.getByDisplayValue('All Vehicles')
    expect(vehicleSelect).toBeInTheDocument()
    
    // Should only have the "All Vehicles" option
    const options = screen.getAllByRole('option')
    const vehicleOptions = options.filter(option => 
      option.closest('select') === vehicleSelect
    )
    expect(vehicleOptions).toHaveLength(1)
    expect(vehicleOptions[0]).toHaveTextContent('All Vehicles')
  })
})