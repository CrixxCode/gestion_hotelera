import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DetailPayment } from './detail-payment';

describe('DetailPayment', () => {
  let component: DetailPayment;
  let fixture: ComponentFixture<DetailPayment>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DetailPayment]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DetailPayment);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
