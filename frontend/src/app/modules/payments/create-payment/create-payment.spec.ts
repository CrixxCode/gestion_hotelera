import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreatePayment } from './create-payment';

describe('CreatePayment', () => {
  let component: CreatePayment;
  let fixture: ComponentFixture<CreatePayment>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreatePayment]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreatePayment);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
