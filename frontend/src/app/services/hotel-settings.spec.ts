import { TestBed } from '@angular/core/testing';

import { HotelSettings } from './hotel-settings';

describe('HotelSettings', () => {
  let service: HotelSettings;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(HotelSettings);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
