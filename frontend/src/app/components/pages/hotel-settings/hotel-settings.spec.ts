import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HotelSettings } from './hotel-settings';

describe('HotelSettings', () => {
  let component: HotelSettings;
  let fixture: ComponentFixture<HotelSettings>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HotelSettings]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HotelSettings);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
